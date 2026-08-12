import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def seed_admin() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="admin",
        display_name="System Admin",
        password="correct-password-123",
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    session.close()


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-password-123"},
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

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_unknown_role_grants_no_admin_access() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    service.create_user(
        username="employee",
        display_name="Employee",
        password="employee-password-123",
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
