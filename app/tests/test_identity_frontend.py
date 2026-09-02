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
    accounts = html.index('/assets/account-management.js')
    application = html.index('/assets/app-v3.js')
    assert runtime < client < gate < demo
    assert application < accounts


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


def test_legacy_profile_action_is_replaced_by_authenticated_identity() -> None:
    source = read("site/assets/identity-gate.js")
    assert "openIdentityProfile(window.HFIdentity.session)" in source
    assert "[data-action='profile-menu']" in source
    assert "event.stopImmediatePropagation()" in source
    assert "data-profile-username" in source
    assert "data-profile-role" in source


def test_account_management_uses_protected_identity_api_and_permissions() -> None:
    html = read("site/index.html")
    source = read("site/assets/account-management.js")
    client = read("site/assets/identity-client.js")
    css = read("site/assets/account-management.css")
    assert '/assets/account-management.css' in html
    assert '/assets/account-management.js' in html
    assert 'can("identity.user.read")' in source
    assert 'can("identity.user.create")' in source
    assert 'can("identity.user.manage")' in source
    assert 'can("identity.role.assign")' in source
    assert "window.HFIdentity.listUsers()" in source
    assert "window.HFIdentity.listRoles()" in source
    assert "window.HFIdentity.listRoleAssignments()" in source
    assert "window.HFIdentity.createUser(input)" in source
    assert "window.HFIdentity.setUserStatus" in source
    assert "window.HFIdentity.assignRole" in source
    assert "window.HFIdentity.revokeRoleAssignment" in source
    assert 'role_code !== "system_administrator" || can(FULL_ACCESS)' in source
    assert 'request("/admin/roles")' in client
    assert 'request("/admin/role-assignments")' in client
    assert 'method: "DELETE"' in client
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "min-height: 44px" in css
    assert "min-height: 48px" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


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
