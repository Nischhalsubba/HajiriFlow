from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def seed_system_admin() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="system.admin",
        display_name="System Admin",
        password="system-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    session.close()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def create_company(client: TestClient, csrf: str, name: str) -> dict:
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


def seed_scoped_workforce_admin(organization_id: str) -> None:
    session = get_session_factory()()
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="workforce.admin",
        display_name="Workforce Admin",
        password="workforce-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code="workforce_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=UUID(organization_id),
    )
    session.commit()
    session.close()


def test_scoped_workforce_admin_isolated_and_context_is_deterministic() -> None:
    seed_system_admin()
    with TestClient(create_app()) as client:
        system_csrf = login(
            client,
            "system.admin",
            "system-admin-password-123",
        )
        primary = create_company(client, system_csrf, "HajiriFlow Nepal")
        other = create_company(client, system_csrf, "Other Tenant")
        seed_scoped_workforce_admin(primary["id"])

        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": system_csrf})
        csrf = login(
            client,
            "workforce.admin",
            "workforce-admin-password-123",
        )

        assert client.get(f"/api/v1/organizations/{other['id']}").status_code == 403

        node_response = client.post(
            f"/api/v1/organizations/{primary['id']}/nodes",
            headers={"X-CSRF-Token": csrf},
            json={
                "node_type": "department",
                "code": "ENG",
                "name": "Engineering",
            },
        )
        assert node_response.status_code == 201, node_response.text
        node = node_response.json()

        employee_response = client.post(
            f"/api/v1/organizations/{primary['id']}/employees",
            headers={"X-CSRF-Token": csrf},
            json={
                "employee_code": "EMP-001",
                "display_name": "Asha Rai",
                "joined_on": "2026-01-01",
            },
        )
        assert employee_response.status_code == 201, employee_response.text
        employee = employee_response.json()

        assignment_response = client.post(
            f"/api/v1/organizations/{primary['id']}/employees/"
            f"{employee['id']}/organization-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "organization_node_id": node["id"],
                "starts_on": "2026-01-01",
                "is_primary": True,
            },
        )
        assert assignment_response.status_code == 201, assignment_response.text

        overlap = client.post(
            f"/api/v1/organizations/{primary['id']}/employees/"
            f"{employee['id']}/organization-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "organization_node_id": node["id"],
                "starts_on": "2026-06-01",
                "is_primary": True,
            },
        )
        assert overlap.status_code == 400
        assert "overlaps" in overlap.json()["detail"]

        shift_response = client.post(
            f"/api/v1/organizations/{primary['id']}/shifts",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "DAY",
                "name": "Day Shift",
                "starts_at": "09:00:00",
                "ends_at": "17:00:00",
                "break_minutes": 60,
                "grace_minutes": 10,
            },
        )
        assert shift_response.status_code == 201, shift_response.text
        shift = shift_response.json()

        shift_assignment = client.post(
            f"/api/v1/organizations/{primary['id']}/shift-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "shift_id": shift["id"],
                "organization_node_id": node["id"],
                "starts_on": "2026-01-01",
            },
        )
        assert shift_assignment.status_code == 201, shift_assignment.text

        context = client.get(
            f"/api/v1/organizations/{primary['id']}/employees/{employee['id']}/context",
            params={"on_date": "2026-09-07"},
        )
        assert context.status_code == 200, context.text
        payload = context.json()
        assert payload["organization_assignment"]["organization_node_id"] == node["id"]
        assert payload["shift"]["id"] == shift["id"]
        assert payload["shift"]["code"] == "DAY"

        denied_cross_tenant_create = client.post(
            f"/api/v1/organizations/{other['id']}/employees",
            headers={"X-CSRF-Token": csrf},
            json={
                "employee_code": "X-001",
                "display_name": "Cross Tenant",
                "joined_on": date.today().isoformat(),
            },
        )
        assert denied_cross_tenant_create.status_code == 403


def test_employee_specific_shift_overrides_department_shift() -> None:
    seed_system_admin()
    with TestClient(create_app()) as client:
        csrf = login(client, "system.admin", "system-admin-password-123")
        organization = create_company(client, csrf, "Shift Test")
        org_id = organization["id"]

        node = client.post(
            f"/api/v1/organizations/{org_id}/nodes",
            headers={"X-CSRF-Token": csrf},
            json={"node_type": "department", "code": "OPS", "name": "Operations"},
        ).json()
        employee = client.post(
            f"/api/v1/organizations/{org_id}/employees",
            headers={"X-CSRF-Token": csrf},
            json={
                "employee_code": "EMP-002",
                "display_name": "Bikash Thapa",
                "joined_on": "2026-01-01",
            },
        ).json()
        client.post(
            f"/api/v1/organizations/{org_id}/employees/"
            f"{employee['id']}/organization-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "organization_node_id": node["id"],
                "starts_on": "2026-01-01",
                "is_primary": True,
            },
        )

        day = client.post(
            f"/api/v1/organizations/{org_id}/shifts",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "DAY",
                "name": "Day",
                "starts_at": "09:00:00",
                "ends_at": "17:00:00",
            },
        ).json()
        late = client.post(
            f"/api/v1/organizations/{org_id}/shifts",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "LATE",
                "name": "Late",
                "starts_at": "12:00:00",
                "ends_at": "20:00:00",
            },
        ).json()
        client.post(
            f"/api/v1/organizations/{org_id}/shift-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "shift_id": day["id"],
                "organization_node_id": node["id"],
                "starts_on": "2026-01-01",
            },
        )
        client.post(
            f"/api/v1/organizations/{org_id}/shift-assignments",
            headers={"X-CSRF-Token": csrf},
            json={
                "shift_id": late["id"],
                "employee_id": employee["id"],
                "starts_on": "2026-09-01",
            },
        )

        context = client.get(
            f"/api/v1/organizations/{org_id}/employees/{employee['id']}/context",
            params={"on_date": "2026-09-07"},
        )
        assert context.status_code == 200
        assert context.json()["shift"]["code"] == "LATE"
