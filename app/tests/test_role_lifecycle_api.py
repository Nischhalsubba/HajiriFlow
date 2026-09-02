import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def seed_role_fixture() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())

    system_admin = service.create_user(
        username="system.admin",
        display_name="System Admin",
        password="system-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=system_admin.id,
        role_code="system_administrator",
        actor_user_id=system_admin.id,
        scope_type=ScopeType.GLOBAL,
    )

    second_system_admin = service.create_user(
        username="second.admin",
        display_name="Second System Admin",
        password="second-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=second_system_admin.id,
        role_code="system_administrator",
        actor_user_id=system_admin.id,
        scope_type=ScopeType.GLOBAL,
    )

    identity_admin = service.create_user(
        username="identity.admin",
        display_name="Identity Admin",
        password="identity-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=identity_admin.id,
        role_code="identity_administrator",
        actor_user_id=system_admin.id,
        scope_type=ScopeType.GLOBAL,
    )

    employee = service.create_user(
        username="employee",
        display_name="Employee",
        password="employee-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=employee.id,
        role_code="employee",
        actor_user_id=identity_admin.id,
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


def assignment_for(assignments: list[dict], username: str, role_code: str, users: list[dict]) -> dict:
    user_id = next(user["id"] for user in users if user["username"] == username)
    return next(
        assignment
        for assignment in assignments
        if assignment["user_id"] == user_id and assignment["role_code"] == role_code
    )


def test_identity_admin_can_inspect_catalog_and_revoke_employee_role() -> None:
    seed_role_fixture()
    with TestClient(create_app()) as client:
        csrf = login(client, "identity.admin", "identity-admin-password-123")

        roles = client.get("/api/v1/admin/roles")
        assert roles.status_code == 200, roles.text
        assert {role["code"] for role in roles.json()} >= {
            "employee",
            "identity_administrator",
            "system_administrator",
        }

        users_response = client.get("/api/v1/admin/users")
        assert users_response.status_code == 200, users_response.text
        users = users_response.json()

        assignments_response = client.get("/api/v1/admin/role-assignments")
        assert assignments_response.status_code == 200, assignments_response.text
        employee_assignment = assignment_for(
            assignments_response.json(), "employee", "employee", users
        )

        no_csrf = client.delete(
            f"/api/v1/admin/role-assignments/{employee_assignment['id']}"
        )
        assert no_csrf.status_code == 403

        revoked = client.delete(
            f"/api/v1/admin/role-assignments/{employee_assignment['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert revoked.status_code == 204, revoked.text

        remaining = client.get("/api/v1/admin/role-assignments")
        assert remaining.status_code == 200
        assert all(
            assignment["id"] != employee_assignment["id"]
            for assignment in remaining.json()
        )

    session = get_session_factory()()
    actions = list(
        session.scalars(
            select(AuditEvent.action).where(AuditEvent.action == "identity.role.revoked")
        )
    )
    session.close()
    assert actions == ["identity.role.revoked"]


def test_identity_admin_cannot_revoke_system_admin_or_own_role() -> None:
    seed_role_fixture()
    with TestClient(create_app()) as client:
        csrf = login(client, "identity.admin", "identity-admin-password-123")
        users = client.get("/api/v1/admin/users").json()
        assignments = client.get("/api/v1/admin/role-assignments").json()

        system_assignment = assignment_for(
            assignments, "second.admin", "system_administrator", users
        )
        denied_system = client.delete(
            f"/api/v1/admin/role-assignments/{system_assignment['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert denied_system.status_code == 403
        assert denied_system.json()["detail"] == (
            "system administrator role requires system administrator access"
        )

        own_assignment = assignment_for(
            assignments, "identity.admin", "identity_administrator", users
        )
        denied_self = client.delete(
            f"/api/v1/admin/role-assignments/{own_assignment['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert denied_self.status_code == 400
        assert denied_self.json()["detail"] == (
            "you cannot revoke your own active role assignment"
        )


def test_system_admin_can_revoke_another_system_admin_role() -> None:
    seed_role_fixture()
    with TestClient(create_app()) as client:
        csrf = login(client, "system.admin", "system-admin-password-123")
        users = client.get("/api/v1/admin/users").json()
        assignments = client.get("/api/v1/admin/role-assignments").json()
        target = assignment_for(
            assignments, "second.admin", "system_administrator", users
        )

        revoked = client.delete(
            f"/api/v1/admin/role-assignments/{target['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert revoked.status_code == 204, revoked.text

        remaining = client.get("/api/v1/admin/role-assignments").json()
        assert all(assignment["id"] != target["id"] for assignment in remaining)
