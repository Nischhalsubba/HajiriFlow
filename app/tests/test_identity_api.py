import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def seed_admin(*, must_change_password: bool = False) -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="admin",
        display_name="System Admin",
        password="correct-password-123",
        must_change_password=must_change_password,
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    session.close()


def seed_identity_admin() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="identity.admin",
        display_name="Identity Admin",
        password="identity-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code="identity_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    protected_admin = service.create_user(
        username="protected.admin",
        display_name="Protected System Admin",
        password="protected-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=protected_admin.id,
        role_code="system_administrator",
        actor_user_id=protected_admin.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    session.close()


def login(client: TestClient, password: str = "correct-password-123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_login_me_admin_create_and_logout() -> None:
    seed_admin()
    with TestClient(create_app()) as client:
        csrf = login(client)

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["username"] == "admin"

        refreshed_csrf = client.get("/api/v1/auth/csrf")
        assert refreshed_csrf.status_code == 200
        assert refreshed_csrf.json()["csrf_token"] == csrf

        users = client.get("/api/v1/admin/users")
        assert users.status_code == 200
        assert len(users.json()) == 1

        denied = client.post(
            "/api/v1/admin/users",
            json={
                "username": "new.user",
                "display_name": "New User",
                "password": "new-user-password-123",
            },
        )
        assert denied.status_code == 403

        created = client.post(
            "/api/v1/admin/users",
            headers={"X-CSRF-Token": csrf},
            json={
                "username": "new.user",
                "display_name": "New User",
                "password": "new-user-password-123",
            },
        )
        assert created.status_code == 201, created.text

        elevated = client.post(
            f"/api/v1/admin/users/{created.json()['id']}/roles",
            headers={"X-CSRF-Token": csrf},
            json={"role_code": "system_administrator", "scope_type": "global"},
        )
        assert elevated.status_code == 201, elevated.text

        disabled = client.patch(
            f"/api/v1/admin/users/{created.json()['id']}/status",
            headers={"X-CSRF-Token": csrf},
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["status"] == "disabled"

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_identity_admin_cannot_manage_system_administrator_privilege() -> None:
    seed_identity_admin()
    with TestClient(create_app()) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "identity.admin",
                "password": "identity-admin-password-123",
            },
        )
        assert login_response.status_code == 200, login_response.text
        csrf = login_response.json()["csrf_token"]

        users = client.get("/api/v1/admin/users")
        assert users.status_code == 200
        protected_admin = next(
            user for user in users.json() if user["username"] == "protected.admin"
        )
        denied_status = client.patch(
            f"/api/v1/admin/users/{protected_admin['id']}/status",
            headers={"X-CSRF-Token": csrf},
            json={"status": "disabled"},
        )
        assert denied_status.status_code == 403
        assert denied_status.json()["detail"] == (
            "system administrator accounts require system administrator access"
        )

        created = client.post(
            "/api/v1/admin/users",
            headers={"X-CSRF-Token": csrf},
            json={
                "username": "target.user",
                "display_name": "Target User",
                "password": "target-user-password-123",
            },
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]

        denied = client.post(
            f"/api/v1/admin/users/{user_id}/roles",
            headers={"X-CSRF-Token": csrf},
            json={"role_code": "system_administrator", "scope_type": "global"},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == (
            "system administrator role requires system administrator access"
        )

        allowed = client.post(
            f"/api/v1/admin/users/{user_id}/roles",
            headers={"X-CSRF-Token": csrf},
            json={"role_code": "employee", "scope_type": "global"},
        )
        assert allowed.status_code == 201, allowed.text


def test_required_password_change_blocks_privileged_actions() -> None:
    seed_admin(must_change_password=True)
    with TestClient(create_app()) as client:
        csrf = login(client)

        denied = client.get("/api/v1/admin/users")
        assert denied.status_code == 403
        assert denied.json()["detail"] == "password change required"

        changed = client.post(
            "/api/v1/auth/change-password",
            headers={"X-CSRF-Token": csrf},
            json={
                "current_password": "correct-password-123",
                "new_password": "replacement-password-456",
            },
        )
        assert changed.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401

        login(client, "replacement-password-456")
        assert client.get("/api/v1/admin/users").status_code == 200


def test_unknown_role_grants_no_admin_access() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    service.create_user(
        username="employee",
        display_name="Employee",
        password="employee-password-123",
        must_change_password=False,
    )
    session.commit()
    session.close()

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "employee", "password": "employee-password-123"},
        )
        assert response.status_code == 200
        assert client.get("/api/v1/admin/users").status_code == 403
