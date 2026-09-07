from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.exceptions import InvalidCredentials
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")

APP_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = APP_ROOT / "src" / "hajiriflow"
SITE_ASSETS = APP_ROOT / "site" / "assets"


def _service() -> tuple[object, IdentityService]:
    session = get_session_factory()()
    seed_identity_catalog(session)
    return session, IdentityService(session, get_settings())


def test_sql_injection_payload_is_treated_as_literal_identity_input() -> None:
    session, service = _service()
    try:
        service.create_user(
            username="security.admin",
            display_name="Security Admin",
            password="security-admin-password-123",
            must_change_password=False,
        )
        session.commit()

        with pytest.raises(InvalidCredentials):
            service.authenticate(
                username="security.admin' OR 1=1 --",
                password="security-admin-password-123",
                client_ip="127.0.0.1",
                user_agent="pytest",
            )
    finally:
        session.close()


def test_fresh_authentication_never_reuses_a_session_token() -> None:
    session, service = _service()
    try:
        service.create_user(
            username="session.user",
            display_name="Session User",
            password="session-user-password-123",
            must_change_password=False,
        )
        session.commit()

        first = service.authenticate(
            username="session.user",
            password="session-user-password-123",
            client_ip="127.0.0.1",
            user_agent="pytest-a",
        )
        second = service.authenticate(
            username="session.user",
            password="session-user-password-123",
            client_ip="127.0.0.1",
            user_agent="pytest-b",
        )

        assert first.token != second.token
        assert first.session.id != second.session.id
    finally:
        session.close()


def test_untrusted_cors_origin_is_not_granted_browser_access() -> None:
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.headers.get("access-control-allow-origin") is None


def test_production_frontend_avoids_raw_html_execution_sinks() -> None:
    forbidden = (
        ".innerHTML",
        "insertAdjacentHTML",
        "document.write(",
        "eval(",
        "new Function(",
    )
    violations: list[str] = []
    for path in sorted(SITE_ASSETS.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                violations.append(f"{path.name}: {token}")

    assert violations == []


def test_backend_has_no_generic_server_side_url_fetch_surface() -> None:
    forbidden = (
        "requests.get(",
        "requests.post(",
        "httpx.get(",
        "httpx.post(",
        "urlopen(",
        "aiohttp.ClientSession",
    )
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                violations.append(f"{path.relative_to(APP_ROOT)}: {token}")

    assert violations == []


def test_no_file_upload_or_redirect_endpoint_is_exposed() -> None:
    api_root = SRC_ROOT / "api"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(api_root.glob("*.py"))
    )

    assert "UploadFile" not in source
    assert "RedirectResponse" not in source
    assert "multipart/form-data" not in source
