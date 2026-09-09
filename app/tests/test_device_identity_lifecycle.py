import json
from datetime import date
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device, DeviceEmployeeMapping, DeviceUser
from hajiriflow.db.models.device_identity import DeviceArchive, DeviceIdentityAction
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.models.workforce_profile import EmployeeProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    DeviceIdentityBundle,
    DeviceUserRecord,
    DeviceWriteResult,
    PullBatch,
)
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.identity_lifecycle import DeviceIdentityLifecycleService
from hajiriflow.device_platform.privacy import BiometricPrivacyService
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


class IdentityAdapter:
    adapter_key = "hajiriflow_gateway_v1"

    def __init__(self, *, exported: dict[str, DeviceIdentityBundle] | None = None) -> None:
        self.exported = exported or {}
        self.pushes: list[tuple[str, bool]] = []
        self.users: dict[str, DeviceIdentityBundle] = {}

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            pull_punches=True,
            historical_pulls=True,
            list_users=True,
            push_users=True,
            biometric_templates=True,
            archive_users=True,
            restore_users=True,
        )

    def diagnostics(self) -> DeviceDiagnostics:
        raise AssertionError("not used")

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        del cursor
        return PullBatch(punches=())

    def list_users(self) -> tuple[DeviceUserRecord, ...]:
        return tuple(
            DeviceUserRecord(
                external_user_id=item.external_user_id,
                display_name=item.display_name,
                privilege=item.privilege,
                active=item.active,
                template_count=item.template_count,
                metadata=item.metadata,
            )
            for item in self.users.values()
        )

    def push_identity(
        self,
        bundle: DeviceIdentityBundle,
        *,
        dry_run: bool,
    ) -> DeviceWriteResult:
        self.pushes.append((bundle.external_user_id, dry_run))
        if not dry_run:
            self.users[bundle.external_user_id] = bundle
        return DeviceWriteResult(accepted=True, code="accepted")

    def export_identity(self, external_user_id: str) -> DeviceIdentityBundle:
        return self.exported[external_user_id]


def _company(session, name: str = "Identity Lifecycle") -> CompanyProfile:
    company = CompanyProfile(legal_name=name, display_name=name)
    session.add(company)
    session.flush()
    return company


def _employee(
    session,
    company: CompanyProfile,
    *,
    code: str,
    attendance_id: int | None,
) -> Employee:
    employee = Employee(
        organization_id=company.id,
        employee_code=code,
        display_name=f"Employee {code}",
        joined_on=date(2026, 1, 1),
    )
    session.add(employee)
    session.flush()
    session.add(
        EmployeeProfile(
            employee_id=employee.id,
            organization_id=company.id,
            attendance_id=attendance_id,
        )
    )
    session.flush()
    return employee


def _device(session, company: CompanyProfile, code: str) -> Device:
    item = Device(
        organization_id=company.id,
        code=code,
        name=code,
        vendor="Gateway",
        adapter_key="hajiriflow_gateway_v1",
        endpoint_uri=f"http://{code.casefold()}.internal",
        capabilities={
            "list_users": True,
            "push_users": True,
            "archive_users": True,
            "restore_users": True,
        },
        pull_interval_seconds=300,
    )
    session.add(item)
    session.flush()
    return item


def _device_user(
    session,
    company: CompanyProfile,
    device: Device,
    *,
    external_user_id: str,
    template_count: int = 0,
) -> DeviceUser:
    item = DeviceUser(
        organization_id=company.id,
        device_id=device.id,
        external_user_id=external_user_id,
        display_name=f"Device {external_user_id}",
        active=True,
        template_count=template_count,
        source_hash=uuid4().hex,
    )
    session.add(item)
    session.flush()
    return item


def _map_user(
    session,
    company: CompanyProfile,
    user: DeviceUser,
    employee: Employee,
) -> None:
    session.add(
        DeviceEmployeeMapping(
            organization_id=company.id,
            employee_id=employee.id,
            device_user_id=user.id,
            status="active",
        )
    )
    session.flush()


def _cipher() -> DeviceSecretCipher:
    key = Fernet.generate_key().decode()
    return DeviceSecretCipher(active_key_id="k1", keys={"k1": key})


def test_compare_device_reports_unknown_and_missing_identities() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        enrolled = _employee(session, company, code="EMP-1", attendance_id=101)
        missing = _employee(session, company, code="EMP-2", attendance_id=102)
        no_attendance_id = _employee(session, company, code="EMP-3", attendance_id=None)
        device = _device(session, company, "GATE-A")
        known_user = _device_user(session, company, device, external_user_id="101")
        _map_user(session, company, known_user, enrolled)
        _device_user(session, company, device, external_user_id="999")

        comparison = DeviceIdentityLifecycleService(session).compare_device(
            organization_id=company.id,
            device_id=device.id,
        )
        assert comparison["registered_count"] == 2
        assert comparison["mapped_count"] == 1
        assert comparison["unknown_count"] == 1
        assert comparison["unknown_users"][0]["external_user_id"] == "999"
        missing_by_id = {
            row["employee_id"]: row for row in comparison["missing_employees"]
        }
        assert missing_by_id[str(missing.id)]["ready_for_enrollment"] is True
        assert missing_by_id[str(no_attendance_id.id)]["ready_for_enrollment"] is False
    finally:
        session.close()


def test_push_preview_must_be_approved_and_rechecks_conflicts() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company, code="EMP-1", attendance_id=101)
        target = _device(session, company, "TARGET")
        service = DeviceIdentityLifecycleService(session)
        actor = uuid4()
        action = service.preview_action(
            organization_id=company.id,
            action_type="push_users",
            requested_by=actor,
            target_device_id=target.id,
            employee_ids=[employee.id],
        )
        assert action.status == "preview"
        assert action.preview_data["blocking_count"] == 0
        with pytest.raises(ValueError, match="preview hash"):
            service.approve_action(
                organization_id=company.id,
                action_id=action.id,
                preview_hash="0" * 64,
                approved_by=actor,
            )
        service.approve_action(
            organization_id=company.id,
            action_id=action.id,
            preview_hash=action.preview_hash,
            approved_by=actor,
        )
        adapter = IdentityAdapter()
        service.execute_action(
            action,
            adapter_resolver=lambda _device: adapter,
            cipher=_cipher(),
        )
        assert action.status == "succeeded"
        assert adapter.pushes == [("101", True), ("101", False)]

        conflicting = service.preview_action(
            organization_id=company.id,
            action_type="push_users",
            requested_by=actor,
            target_device_id=target.id,
            employee_ids=[employee.id],
        )
        assert conflicting.preview_data["blocking_count"] == 1
        with pytest.raises(ValueError, match="blocking conflicts"):
            service.approve_action(
                organization_id=company.id,
                action_id=conflicting.id,
                preview_hash=conflicting.preview_hash,
                approved_by=actor,
            )
    finally:
        session.close()


def test_biometric_migration_requires_consent_and_never_overwrites() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company, code="EMP-1", attendance_id=101)
        source = _device(session, company, "SOURCE")
        target = _device(session, company, "TARGET")
        source_user = _device_user(
            session,
            company,
            source,
            external_user_id="101",
            template_count=2,
        )
        _map_user(session, company, source_user, employee)
        service = DeviceIdentityLifecycleService(session)
        actor = uuid4()

        blocked = service.preview_action(
            organization_id=company.id,
            action_type="migrate_users",
            requested_by=actor,
            source_device_id=source.id,
            target_device_id=target.id,
            device_user_ids=[source_user.id],
        )
        assert blocked.preview_data["blocking_count"] == 1
        assert blocked.preview_data["rows"][0]["code"] == "biometric_consent_not_granted"

        BiometricPrivacyService(session).record_consent(
            organization_id=company.id,
            employee_id=employee.id,
            decision="granted",
            policy_version="v1",
            purpose="device migration",
            actor_user_id=None,
        )
        action = service.preview_action(
            organization_id=company.id,
            action_type="migrate_users",
            requested_by=actor,
            source_device_id=source.id,
            target_device_id=target.id,
            device_user_ids=[source_user.id],
        )
        service.approve_action(
            organization_id=company.id,
            action_id=action.id,
            preview_hash=action.preview_hash,
            approved_by=actor,
        )
        exported = DeviceIdentityBundle(
            external_user_id="101",
            display_name="Employee EMP-1",
            template_count=2,
            biometric_payload="opaque-biometric-template",
        )
        source_adapter = IdentityAdapter(exported={"101": exported})
        target_adapter = IdentityAdapter()
        service.execute_action(
            action,
            adapter_resolver=lambda device: (
                source_adapter if device.id == source.id else target_adapter
            ),
            cipher=_cipher(),
        )
        assert action.status == "succeeded"
        assert target_adapter.pushes == [("101", True), ("101", False)]

        target_user = session.scalar(
            select(DeviceUser).where(
                DeviceUser.device_id == target.id,
                DeviceUser.external_user_id == "101",
            )
        )
        assert target_user is not None
        conflict = service.preview_action(
            organization_id=company.id,
            action_type="migrate_users",
            requested_by=actor,
            source_device_id=source.id,
            target_device_id=target.id,
            device_user_ids=[source_user.id],
        )
        assert conflict.preview_data["blocking_count"] == 1
        assert conflict.preview_data["rows"][0]["code"] == "target_external_id_conflict"
    finally:
        session.close()


def test_archive_is_encrypted_and_restore_is_previewed() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company, code="EMP-1", attendance_id=101)
        source = _device(session, company, "SOURCE")
        target = _device(session, company, "TARGET")
        user = _device_user(
            session,
            company,
            source,
            external_user_id="101",
            template_count=1,
        )
        _map_user(session, company, user, employee)
        BiometricPrivacyService(session).record_consent(
            organization_id=company.id,
            employee_id=employee.id,
            decision="granted",
            policy_version="v1",
            purpose="encrypted backup",
            actor_user_id=None,
        )
        service = DeviceIdentityLifecycleService(session)
        actor = uuid4()
        cipher = _cipher()
        export_action = service.preview_action(
            organization_id=company.id,
            action_type="archive_export",
            requested_by=actor,
            source_device_id=source.id,
            device_user_ids=[user.id],
        )
        service.approve_action(
            organization_id=company.id,
            action_id=export_action.id,
            preview_hash=export_action.preview_hash,
            approved_by=actor,
        )
        bundle = DeviceIdentityBundle(
            external_user_id="101",
            display_name="Employee EMP-1",
            template_count=1,
            biometric_payload="super-secret-biometric-template",
        )
        source_adapter = IdentityAdapter(exported={"101": bundle})
        service.execute_action(
            export_action,
            adapter_resolver=lambda _device: source_adapter,
            cipher=cipher,
        )
        assert export_action.status == "succeeded"
        archive_id = UUID(export_action.result_data["archive_id"])
        archive = session.get(DeviceArchive, archive_id)
        assert archive is not None
        assert b"super-secret-biometric-template" not in archive.ciphertext
        assert "biometric_payload" not in json.dumps(archive.manifest_data)
        assert archive.manifest_data["rows"][0]["template_count"] == 1

        restore_action = service.preview_action(
            organization_id=company.id,
            action_type="archive_restore",
            requested_by=actor,
            target_device_id=target.id,
            archive_id=archive.id,
        )
        assert restore_action.preview_data["blocking_count"] == 0
        service.approve_action(
            organization_id=company.id,
            action_id=restore_action.id,
            preview_hash=restore_action.preview_hash,
            approved_by=actor,
        )
        target_adapter = IdentityAdapter()
        service.execute_action(
            restore_action,
            adapter_resolver=lambda _device: target_adapter,
            cipher=cipher,
        )
        assert restore_action.status == "succeeded"
        assert target_adapter.pushes == [("101", True), ("101", False)]
        assert archive.status == "restored"
    finally:
        session.close()


def _seed_user(
    *,
    username: str,
    password: str,
    role_code: str,
    organization_id: str | None = None,
) -> UUID:
    session = get_session_factory()()
    seed_identity_catalog(session)
    identity = IdentityService(session, get_settings())
    user = identity.create_user(
        username=username,
        display_name=username,
        password=password,
        must_change_password=False,
    )
    identity.assign_role(
        user_id=user.id,
        role_code=role_code,
        actor_user_id=user.id,
        scope_type=(ScopeType.ORGANIZATION if organization_id else ScopeType.GLOBAL),
        scope_id=UUID(organization_id) if organization_id else None,
    )
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_identity_action_api_is_csrf_and_tenant_scoped() -> None:
    _seed_user(
        username="system.admin",
        password="system-admin-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(client, "system.admin", "system-admin-password-123")
        primary = client.post(
            "/api/v1/organizations",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "legal_name": "Primary Pvt. Ltd.",
                "display_name": "Primary",
                "timezone": "Asia/Kathmandu",
            },
        ).json()
        other = client.post(
            "/api/v1/organizations",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "legal_name": "Other Pvt. Ltd.",
                "display_name": "Other",
                "timezone": "Asia/Kathmandu",
            },
        ).json()
        admin_user_id = _seed_user(
            username="device.admin",
            password="device-admin-password-123",
            role_code="workforce_administrator",
            organization_id=primary["id"],
        )
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": system_csrf})
        csrf = _login(client, "device.admin", "device-admin-password-123")

        session = get_session_factory()()
        try:
            company = session.get(CompanyProfile, UUID(primary["id"]))
            assert company is not None
            employee = _employee(session, company, code="EMP-1", attendance_id=101)
            target = _device(session, company, "TARGET")
            session.commit()
            employee_id = employee.id
            target_id = target.id
        finally:
            session.close()

        payload = {
            "action_type": "push_users",
            "target_device_id": str(target_id),
            "employee_ids": [str(employee_id)],
        }
        no_csrf = client.post(
            f"/api/v1/organizations/{primary['id']}/device-identities/actions/preview",
            json=payload,
        )
        assert no_csrf.status_code == 403
        preview = client.post(
            f"/api/v1/organizations/{primary['id']}/device-identities/actions/preview",
            headers={"X-CSRF-Token": csrf},
            json=payload,
        )
        assert preview.status_code == 201, preview.text
        action_id = preview.json()["id"]
        cross_tenant = client.get(
            f"/api/v1/organizations/{other['id']}/device-identities/actions/{action_id}"
        )
        assert cross_tenant.status_code == 403
        approval = client.post(
            f"/api/v1/organizations/{primary['id']}/device-identities/actions/{action_id}/approve",
            headers={"X-CSRF-Token": csrf},
            json={"preview_hash": preview.json()["preview_hash"]},
        )
        assert approval.status_code == 200, approval.text
        assert approval.json()["status"] == "approved"
        assert admin_user_id is not None

        session = get_session_factory()()
        try:
            stored = session.get(DeviceIdentityAction, UUID(action_id))
            assert stored is not None
            assert stored.status == "approved"
        finally:
            session.close()
