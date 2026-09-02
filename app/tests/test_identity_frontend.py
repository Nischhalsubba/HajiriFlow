from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = APP_ROOT / "site"


def read(relative: str) -> str:
    return (APP_ROOT / relative).read_text(encoding="utf-8")


def test_workspace_is_locked_behind_identity_bootstrap() -> None:
    html = read("site/index.html")
    assert 'class="app-is-loading identity-locked"' in html
    assert 'id="identity-gate"' in html
    assert 'id="app-shell" inert aria-hidden="true"' in html
    assert 'data-current-user-name' in html
    assert 'data-current-user-role' in html
    assert 'data-identity-logout' in html
    assert "Nischhal Subba" not in html


def test_identity_scripts_load_before_demo_application_state() -> None:
    html = read("site/index.html")
    runtime = html.index('/assets/runtime-config.js')
    client = html.index('/assets/identity-client.js')
    gate = html.index('/assets/identity-gate.js')
    demo = html.index('/assets/demo-engine.js')
    assert runtime < client < gate < demo


def test_identity_client_uses_same_origin_cookie_session_and_csrf_refresh() -> None:
    source = read("site/assets/identity-client.js")
    assert 'apiBasePath || "/api"' in source
    assert 'credentials: "same-origin"' in source
    assert 'request("/auth/csrf")' in source
    assert 'headers["X-CSRF-Token"] = csrfToken' in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_auth_gate_enforces_required_password_change() -> None:
    source = read("site/assets/identity-gate.js")
    assert "must_change_password" in source
    assert "window.HFIdentity.changePassword" in source
    assert "window.HFIdentity.logout" in source
    assert "unlockApplication(session)" in source


def test_netlify_keeps_browser_api_same_origin() -> None:
    config = (APP_ROOT.parent / "netlify.toml").read_text(encoding="utf-8")
    generator = read("scripts/generate-runtime-config.mjs")
    assert 'command = "node scripts/generate-runtime-config.mjs"' in config
    assert "connect-src 'self'" in config
    assert "Production builds require HAJIRIFLOW_API_BASE_URL." in generator
    assert "/api/* ${upstream}/api/:splat 200" in generator
    assert "apiBasePath: \"/api\"" in generator


def test_identity_gate_has_accessible_interaction_baseline() -> None:
    css = read("site/assets/auth.css")
    assert "min-height: 48px" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert "prefers-contrast: more" in css
