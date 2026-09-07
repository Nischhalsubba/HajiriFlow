from datetime import date

import pytest
from sqlalchemy import select

from hajiriflow.db.models.biometric import BiometricConsentEvent
from hajiriflow.db.models.device import Device, DeviceEmployeeMapping, DeviceUser
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.privacy import BiometricPrivacyService
from hajiriflow.identity.bootstrap import ROLES


def _fixtures(session):
    organization = CompanyProfile(legal_name="Acme", display_name="Acme")
    session.add(organization)
    session.flush()
    employee = Employee(
        organization_id=organization.id,
        employee_code="E-001",
        display_name="Test Employee",
        joined_on=date(2026, 1, 1),
    )
    device = Device(
        organization_id=organization.id,
        code="front-gate",
        name="Front gate",
        vendor="test-vendor",
        model="virtual",
        serial_number="serial-privacy",
        adapter_key="test",
        endpoint_uri="test://front-gate",
        capabilities={"pull_punches": True},
    )
    session.add_all([employee, device])
    session.flush()
    device_user = DeviceUser(
        organization_id=organization.id,
        device_id=device.id,
        external_user_id="42",
        display_name="Test Employee",
        privilege="user",
        active=True,
        template_count=1,
        source_hash="a" * 64,
    )
    session.add(device_user)
    session.flush()
    mapping = DeviceEmployeeMapping(
        organization_id=organization.id,
        device_user_id=device_user.id,
        employee_id=employee.id,
        status="active",
    )
    session.add(mapping)
    session.flush()
    return organization, employee, device_user, mapping


def test_consent_history_is_append_only_and_latest_decision_wins(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, employee, _, _ = _fixtures(session)
        service = BiometricPrivacyService(session)
        granted = service.record_consent(
            organization_id=organization.id,
            employee_id=employee.id,
            decision="granted",
            policy_version="2026-09",
            purpose="attendance verification at an enrolled device",
            actor_user_id=None,
        )
        revoked = service.record_consent(
            organization_id=organization.id,
            employee_id=employee.id,
            decision="revoked",
            policy_version="2026-09",
            purpose="attendance verification at an enrolled device",
            actor_user_id=None,
        )
        session.flush()

        assert service.latest_consent(
            organization_id=organization.id,
            employee_id=employee.id,
        ).id == revoked.id
        assert session.scalars(select(BiometricConsentEvent)).all() == [granted, revoked]
        assert session.scalars(
            select(AuditEvent).where(AuditEvent.action.like("biometric.consent.%"))
        ).all()

        granted.decision = "declined"
        with pytest.raises(RuntimeError, match="append-only"):
            session.flush()
        session.rollback()
    finally:
        session.close()


def test_deletion_request_disables_mapping_and_requires_external_receipt(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, _, device_user, mapping = _fixtures(session)
        service = BiometricPrivacyService(session)
        request = service.request_deletion(
            organization_id=organization.id,
            device_user_id=device_user.id,
            reason="employee revoked biometric consent",
            actor_user_id=None,
        )
        session.flush()

        assert request.status == "pending"
        assert mapping.status == "disabled"
        assert device_user.active is False

        with pytest.raises(ValueError, match="SHA-256"):
            service.complete_deletion(
                organization_id=organization.id,
                request_id=request.id,
                external_receipt_hash="raw-provider-receipt-must-not-be-stored",
                actor_user_id=None,
            )

        receipt_hash = "b" * 64
        completed = service.complete_deletion(
            organization_id=organization.id,
            request_id=request.id,
            external_receipt_hash=receipt_hash,
            actor_user_id=None,
        )
        session.flush()
        assert completed.status == "completed"
        assert completed.external_receipt_hash == receipt_hash
        assert completed.completed_at is not None
    finally:
        session.close()


def test_biometric_privileges_are_not_part_of_general_workforce_admin_role() -> None:
    workforce_permissions = ROLES["workforce_administrator"]["permissions"]
    biometric_permissions = ROLES["biometric_administrator"]["permissions"]

    assert "biometric.consent.manage" not in workforce_permissions
    assert "biometric.deletion.manage" not in workforce_permissions
    assert {
        "biometric.consent.read",
        "biometric.consent.manage",
        "biometric.deletion.manage",
    }.issubset(biometric_permissions)
