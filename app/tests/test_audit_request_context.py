from hajiriflow.core.request_context import bind_request_id, reset_request_id
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.session import get_session_factory


def test_audit_events_inherit_bound_request_id(database) -> None:
    del database
    session = get_session_factory()()
    token = bind_request_id("request-audit-123")
    try:
        event = AuditEvent(
            action="attendance.correction.approved",
            object_type="attendance_record",
            object_id="attendance-1",
            after_data={"status": "approved"},
            context_data={"organization_id": "org-1"},
        )
        session.add(event)
        session.flush()
        assert event.request_id == "request-audit-123"
        assert event.context_data["organization_id"] == "org-1"
        assert event.context_data["source"] == "attendance"
    finally:
        reset_request_id(token)
        session.close()


def test_explicit_audit_request_id_is_preserved(database) -> None:
    del database
    session = get_session_factory()()
    token = bind_request_id("request-context")
    try:
        event = AuditEvent(
            action="system.import",
            object_type="import_job",
            object_id="job-1",
            request_id="external-job-correlation",
        )
        session.add(event)
        session.flush()
        assert event.request_id == "external-job-correlation"
    finally:
        reset_request_id(token)
        session.close()
