import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def _seed() -> tuple[str, str]:
    session = get_session_factory()()
    try:
        seed_identity_catalog(session)
        first = CompanyProfile(
            legal_name="First Organization Pvt. Ltd.",
            display_name="First Organization",
        )
        second = CompanyProfile(
            legal_name="Second Organization Pvt. Ltd.",
            display_name="Second Organization",
        )
        session.add_all([first, second])
        session.flush()

        service = IdentityService(session, get_settings())
        system = service.create_user(
            username="organization.system",
            display_name="Organization System Admin",
            password="organization-system-password-123",
            must_change_password=False,
        )
        service.assign_role(
            user_id=system.id,
            role_code="system_administrator",
            actor_user_id=system.id,
            scope_type=ScopeType.GLOBAL,
        )

        scoped = service.create_user(
            username="organization.scoped",
            display_name="Organization Scoped Admin",
            password="organization-scoped-password-123",
            must_change_password=False,
        )
        service.assign_role(
            user_id=scoped.id,
            role_code="workforce_administrator",
            actor_user_id=system.id,
            scope_type=ScopeType.ORGANIZATION,
            scope_id=first.id,
        )
        session.commit()
        return str(first.id), str(second.id)
    finally:
        session.close()


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text


def test_global_admin_discovers_all_active_organizations() -> None:
    first_id, second_id = _seed()
    with TestClient(create_app()) as client:
        _login(
            client,
            "organization.system",
            "organization-system-password-123",
        )
        response = client.get("/api/v1/organizations")
        assert response.status_code == 200, response.text
        ids = {item["id"] for item in response.json()}
        assert ids == {first_id, second_id}


def test_scoped_admin_discovers_only_its_authorized_organization() -> None:
    first_id, second_id = _seed()
    with TestClient(create_app()) as client:
        _login(
            client,
            "organization.scoped",
            "organization-scoped-password-123",
        )
        response = client.get("/api/v1/organizations")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert [item["id"] for item in payload] == [first_id]
        assert second_id not in {item["id"] for item in payload}
