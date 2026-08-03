from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
APP = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "site" / "assets").glob("*.js"))
)
CSS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "site" / "assets").glob("styles*.css"))
)
NETLIFY = (ROOT / "netlify.toml").read_text(encoding="utf-8")


def test_frontend_assets_are_declared() -> None:
    for asset in (
        "styles.css",
        "styles-components.css",
        "styles-responsive.css",
        "core.js",
        "views-workforce.js",
        "views-operations.js",
        "ui-core.js",
        "forms.js",
        "app.js",
        "enhancements.js",
    ):
        assert f'/assets/{asset}' in INDEX
    assert 'id="workspace"' in INDEX
    assert 'id="primary-nav"' in INDEX


def test_static_shell_uses_external_code_and_styles() -> None:
    assert "<script>" not in INDEX
    assert 'style="' not in INDEX


def test_all_primary_routes_have_views() -> None:
    for route in (
        "overview",
        "attendance",
        "employees",
        "leave",
        "reports",
        "devices",
        "payroll",
        "organization",
        "settings",
    ):
        assert f"{route}:" in APP


def test_core_prototype_actions_are_implemented() -> None:
    for action in (
        "add-employee",
        "manual-attendance",
        "request-leave",
        "add-device",
        "create-payroll-draft",
        "reset-demo",
    ):
        assert f'case "{action}"' in APP


def test_accessibility_and_responsive_guards_exist() -> None:
    assert "prefers-reduced-motion" in CSS
    assert ":focus-visible" in CSS
    assert "@media (max-width: 760px)" in CSS
    assert 'class="skip-link"' in INDEX
    assert 'aria-live="polite"' in INDEX


def test_netlify_serves_the_site_with_strict_local_assets() -> None:
    assert 'publish = "site"' in NETLIFY
    assert "script-src 'self'" in NETLIFY
    assert "style-src 'self'" in NETLIFY
