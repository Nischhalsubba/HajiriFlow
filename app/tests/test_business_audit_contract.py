import pytest
from sqlalchemy import select

from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.audit import REDACTED

pytestmark = pytest.mark.usefixtures("database")


def test_payroll_approval_audit_is_completed_before_persistence() -> None:
    session = get_session_factory()()
    try:
        event = AuditEvent(
            action="payroll.run.approved",
            object_type="payroll_run",
            object_id="run-123",
            after_data={"status": "approved", "bank_account": "should-not-survive"},
            context_data={
                "organization_id": "org-123",
                "token": "should-not-survive",
            },
        )
        session.add(event)
        session.flush()

        stored = session.scalar(select(AuditEvent).where(AuditEvent.id == event.id))
        assert stored is not None
        assert stored.request_id is not None
        assert stored.request_id.startswith("op-")
        assert stored.before_data == {"status": "pending_approval"}
        assert stored.after_data == {"status": "approved", "bank_account": REDACTED}
        assert stored.context_data == {
            "organization_id": "org-123",
            "token": REDACTED,
            "source": "payroll",
            "actor_reference": "system",
            "actor_type": "system",
            "approval_reference": "run-123",
        }
    finally:
        session.rollback()
        session.close()


def test_device_credential_rotation_records_previous_version() -> None:
    session = get_session_factory()()
    try:
        event = AuditEvent(
            action="device.credential.rotate",
            object_type="device",
            object_id="device-123",
            after_data={"credential_version": 2, "key_id": "k2"},
            context_data={"organization_id": "org-123"},
        )
        session.add(event)
        session.flush()

        assert event.before_data == {"credential_version": 1}
        assert event.context_data["source"] == "device"
        assert event.context_data["actor_reference"] == "system"
    finally:
        session.rollback()
        session.close()


def test_business_audit_rejects_missing_organization_context() -> None:
    session = get_session_factory()()
    try:
        session.add(
            AuditEvent(
                action="biometric.deletion.complete",
                object_type="biometric_deletion_request",
                object_id="request-123",
                after_data={"status": "completed"},
            )
        )
        with pytest.raises(ValueError, match="requires organization_id context"):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_business_audit_rejects_missing_new_state_snapshot() -> None:
    session = get_session_factory()()
    try:
        session.add(
            AuditEvent(
                action="attendance.correction_approved",
                object_type="attendance_record",
                object_id="record-123",
                context_data={"organization_id": "org-123"},
            )
        )
        with pytest.raises(ValueError, match="requires a redacted new-state snapshot"):
            session.flush()
    finally:
        session.rollback()
        session.close()
