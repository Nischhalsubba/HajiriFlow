from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import ROLES, seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")

PAYROLL_PERMISSIONS = {
    "payroll.read",
    "payroll.manage",
    "payroll.approve",
    "payroll.export",
}


def _seed_user(
    *,
    username: str,
    password: str,
    role_code: str,
    organization_id: str | None = None,
) -> None:
    session = get_session_factory()()
    try:
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
            scope_type=(
                ScopeType.ORGANIZATION if organization_id else ScopeType.GLOBAL
            ),
            scope_id=UUID(organization_id) if organization_id else None,
        )
        session.commit()
    finally:
        session.close()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def _create_organization(client: TestClient, csrf: str) -> dict:
    response = client.post(
        "/api/v1/organizations",
        headers={"X-CSRF-Token": csrf},
        json={
            "legal_name": "Sensitive Access Test Pvt. Ltd.",
            "display_name": "Sensitive Access Test",
            "timezone": "Asia/Kathmandu",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assert_payroll_denied(client: TestClient, organization_id: str) -> None:
    missing_run = uuid4()
    paths = (
        f"/api/v1/organizations/{organization_id}/payroll/periods",
        f"/api/v1/organizations/{organization_id}/payroll/runs",
        f"/api/v1/organizations/{organization_id}/payroll/runs/{missing_run}/lines",
        f"/api/v1/organizations/{organization_id}/payroll/runs/{missing_run}/history",
        f"/api/v1/organizations/{organization_id}/payroll/runs/{missing_run}/export",
        f"/api/v1/organizations/{organization_id}/reports/payroll/{missing_run}/worksheet",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["detail"] == "permission denied"


def test_nonpayroll_roles_do_not_gain_salary_permissions() -> None:
    for role_code in ("workforce_administrator", "biometric_administrator", "employee"):
        permissions = set(ROLES[role_code]["permissions"])
        assert permissions.isdisjoint(PAYROLL_PERMISSIONS), role_code


def test_workforce_admin_can_read_workforce_but_not_salary_or_payroll() -> None:
    _seed_user(
        username="system.admin",
        password="system-admin-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(
            client,
            "system.admin",
            "system-admin-password-123",
        )
        organization = _create_organization(client, system_csrf)
        _seed_user(
            username="workforce.admin",
            password="workforce-admin-password-123",
            role_code="workforce_administrator",
            organization_id=organization["id"],
        )
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": system_csrf},
        )
        assert logout.status_code == 204

        _login(
            client,
            "workforce.admin",
            "workforce-admin-password-123",
        )
        workforce = client.get(
            f"/api/v1/organizations/{organization['id']}/employees"
        )
        assert workforce.status_code == 200, workforce.text
        _assert_payroll_denied(client, organization["id"])


def test_biometric_admin_cannot_cross_into_payroll_domain() -> None:
    _seed_user(
        username="system.admin.biometric",
        password="system-admin-biometric-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(
            client,
            "system.admin.biometric",
            "system-admin-biometric-password-123",
        )
        organization = _create_organization(client, system_csrf)
        _seed_user(
            username="biometric.admin",
            password="biometric-admin-password-123",
            role_code="biometric_administrator",
            organization_id=organization["id"],
        )
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": system_csrf},
        )
        assert logout.status_code == 204

        _login(
            client,
            "biometric.admin",
            "biometric-admin-password-123",
        )
        _assert_payroll_denied(client, organization["id"])
