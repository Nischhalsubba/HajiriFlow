from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
ENGINE = (ROOT / "site" / "assets" / "demo-engine.js").read_text(encoding="utf-8")
APP = (ROOT / "site" / "assets" / "app-v3.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "assets" / "hajiriflow-v3.css").read_text(encoding="utf-8")
NETLIFY = (ROOT / "netlify.toml").read_text(encoding="utf-8")


def test_v3_assets_are_declared() -> None:
    for asset in ("hajiriflow-v3.css", "demo-engine.js", "app-v3.js"):
        assert f"/assets/{asset}" in INDEX
    assert 'id="workspace"' in INDEX
    assert 'id="primary-nav"' in INDEX
    assert 'id="modal-layer"' in INDEX
    assert 'id="command-layer"' in INDEX


def test_shell_contains_no_operational_rows() -> None:
    assert "Aarav" not in INDEX
    assert "Present employees" not in INDEX
    assert "66 capabilities" not in INDEX
    assert "seedState" not in ENGINE
    assert "employees: [" not in ENGINE
    assert "attendance: [" not in ENGINE


def test_demo_data_is_generated_and_persisted() -> None:
    for marker in (
        "generateState",
        "buildEmployees",
        "buildAttendance",
        "buildLeaveRequests",
        "buildDevices",
        "buildPayrollPeriods",
        "localStorage.setItem",
        "regenerate",
    ):
        assert marker in ENGINE


def test_all_primary_routes_have_dynamic_views() -> None:
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
        assert f"{route}: render" in APP


def test_core_demo_actions_are_implemented() -> None:
    for action in (
        "add-employee",
        "manual-attendance",
        "request-leave",
        "add-device",
        "generate-payroll",
        "regenerate-demo",
        "export-snapshot",
    ):
        assert f'case "{action}"' in APP


def test_accessibility_responsive_and_component_states_exist() -> None:
    assert "prefers-reduced-motion" in CSS
    assert ":focus-visible" in CSS
    assert "@media (max-width: 760px)" in CSS
    assert "status-success" in CSS
    assert "status-warning" in CSS
    assert "status-danger" in CSS
    assert 'class="skip-link"' in INDEX
    assert 'aria-live="polite"' in INDEX


def test_netlify_serves_strict_same_origin_assets() -> None:
    assert 'publish = "site"' in NETLIFY
    assert "script-src 'self'" in NETLIFY
    assert "style-src 'self'" in NETLIFY
    assert "max-age=0, must-revalidate" in NETLIFY
