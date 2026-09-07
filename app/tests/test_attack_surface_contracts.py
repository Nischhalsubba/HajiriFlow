import hashlib
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

# These legacy renderers still use HTML-string templates. Their current blobs were
# manually reviewed for escaping/textContent boundaries. Any edit changes the blob
# SHA and forces a deliberate re-review before CI can pass.
REVIEWED_INNER_HTML_BLOBS = {
    "account-management.js": "9d984c6f247322b8a7ce87951e1d55a65d1be91b",
    "app-v3.js": "b9690ae96147e4c77270f7abf1b4a3303cc37857",
    "core.js": "ce07da5f73d57911be1cac004168e646652dcc5b",
    "forms.js": "6ef11055a2bcd752db9297fcde4c5b4e8876265c",
    "identity-gate.js": "7d9572722a781c47c60f32c6a276700dc112344e",
    "ui-core.js": "c2614b3346b4396d3647b595666e570d7db5a177",
}


def _service() -> tuple[object, IdentityService]:
    session = get_session_factory()()
    seed_identity_catalog(session)
    return session, IdentityService(session, get_settings())


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    payload = f"blob {len(data)}\0".encode() + data
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


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


def test_frontend_html_execution_sinks_are_change_controlled() -> None:
    permanently_forbidden = (
        "insertAdjacentHTML",
        "document.write(",
        "eval(",
        "new Function(",
    )
    violations: list[str] = []
    for path in sorted(SITE_ASSETS.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        for token in permanently_forbidden:
            if token in source:
                violations.append(f"{path.name}: forbidden {token}")

        if ".innerHTML" not in source:
            continue
        expected_sha = REVIEWED_INNER_HTML_BLOBS.get(path.name)
        if expected_sha is None:
            violations.append(f"{path.name}: unreviewed innerHTML sink")
            continue
        actual_sha = _git_blob_sha(path)
        if actual_sha != expected_sha:
            violations.append(
                f"{path.name}: reviewed sink changed ({actual_sha}); security re-review required"
            )

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


def test_no_server_file_upload_or_redirect_endpoint_is_exposed() -> None:
    api_root = SRC_ROOT / "api"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(api_root.glob("*.py"))
    )

    assert "UploadFile" not in source
    assert "RedirectResponse" not in source
    assert "multipart/form-data" not in source


def test_production_employee_photos_are_not_browser_persisted() -> None:
    production_source = (SITE_ASSETS / "production-v7.js").read_text(encoding="utf-8")
    media_source = (SITE_ASSETS / "media-v5.js").read_text(encoding="utf-8")

    assert 'type="file"' not in production_source
    assert "FileReader" not in production_source
    assert "localStorage" not in media_source
    assert "hajiriflow_employee_photos" not in media_source
