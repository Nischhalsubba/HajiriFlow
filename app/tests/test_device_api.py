from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import DeviceUser
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def _seed_user(
    *,
    username: str,
    password: str,
    role_code: str,
    organization_id: str | None = None,
) -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username=username,
        display_name=username,
        password=password,
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code=role_code,
        actor_user_id=user.id,
        scope_type=(ScopeType.ORGANIZATION if organization_id else ScopeType.GLOBAL),
        scope_id=UUID(organization_id) if organization_id else None,
    )
    session.commit()
    session.close()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def _create_company(client: TestClient, csrf: str, name: str) -> dict:
    response = client.post(
        "/api/v1/organizations",
        headers={"X-CSRF-Token": csrf},
        json={
            "legal_name": f"{name} Pvt. Ltd.",
            "display_name": name,
            "timezone": "Asia/Kathmandu",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_device_api_is_scoped_and_exposes_no_credential_ciphertext() -> None:
    _seed_user(
        username="system.admin",
        password="system-admin-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(client, "system.admin", "system-admin-password-123")
        primary = _create_company(client, system_csrf, "Device Tenant")
        other = _create_company(client, system_csrf, "Other Tenant")
        employee_response = client.post(
            f"/api/v1/organizations/{primary['id']}/employees",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "employee_code": "EMP-DEV-1",
                "display_name": "Kiran Rai",
                "joined_on": "2026-01-01",
            },
        )
        assert employee_response.status_code == 201, employee_response.text
        employee = employee_response.json()

        _seed_user(
            username="device.admin",
            password="device-admin-password-123",
            role_code="workforce_administrator",
            organization_id=primary["id"],
        )
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": system_csrf})
        csrf = _login(client, "device.admin", "device-admin-password-123")

        missing_csrf = client.post(
            f"/api/v1/organizations/{primary['id']}/devices",
            json={
                "code": "GATE-1",
                "name": "Main Gate",
                "vendor": "Unspecified",
                "adapter_key": "unsupported-test-adapter",
                "endpoint_uri": "device://main-gate",
            },
        )
        assert missing_csrf.status_code == 403

        created = client.post(
            f"/api/v1/organizations/{primary['id']}/devices",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "GATE-1",
                "name": "Main Gate",
                "vendor": "Unspecified",
                "adapter_key": "unsupported-test-adapter",
                "endpoint_uri": "device://main-gate",
                "capabilities": {"pull_punches": True},
                "pull_interval_seconds": 300,
            },
        )
        assert created.status_code == 201, created.text
        device = created.json()
        assert device["status"] == "active"

        assert client.get(
            f"/api/v1/organizations/{other['id']}/devices"
        ).status_code == 403

        credentials = client.get(
            f"/api/v1/organizations/{primary['id']}/devices/{device['id']}/credentials"
        )
        assert credentials.status_code == 200, credentials.text
        assert credentials.json() == []
        assert "ciphertext" not in credentials.text

        disabled = client.patch(
            f"/api/v1/organizations/{primary['id']}/devices/{device['id']}/status",
            headers={"X-CSRF-Token": csrf},
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["status"] == "disabled"

        session = get_session_factory()()
        try:
            device_user = DeviceUser(
                organization_id=UUID(primary["id"]),
                device_id=UUID(device["id"]),
                external_user_id="device-user-101",
                display_name="Kiran Rai",
                privilege="user",
                active=True,
                template_count=1,
                source_hash="a" * 64,
            )
            session.add(device_user)
            session.commit()
            device_user_id = str(device_user.id)
        finally:
            session.close()

        users = client.get(
            f"/api/v1/organizations/{primary['id']}/devices/{device['id']}/users"
        )
        assert users.status_code == 200, users.text
        assert users.json()[0]["template_count"] == 1
        assert "template" not in {key.lower() for key in users.json()[0] if key != "template_count"}

        mapped = client.post(
            f"/api/v1/organizations/{primary['id']}/devices/mappings",
            headers={"X-CSRF-Token": csrf},
            json={
                "device_user_id": device_user_id,
                "employee_id": employee["id"],
            },
        )
        assert mapped.status_code == 201, mapped.text
        assert mapped.json()["employee_id"] == employee["id"]

        mapping_list = client.get(
            f"/api/v1/organizations/{primary['id']}/devices/mappings/all"
        )
        assert mapping_list.status_code == 200, mapping_list.text
        assert len(mapping_list.json()) == 1
