from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_generator_marks_production_as_integration_required() -> None:
    source = _read("scripts/generate-runtime-config.mjs")
    assert 'environment: isProduction ? "production" : "development"' in source
    assert 'operationalDataMode: isProduction ? "integration-required" : "demo"' in source
    assert 'Production builds require HAJIRIFLOW_API_BASE_URL.' in source


def test_production_layer_does_not_relabel_demo_data_as_live() -> None:
    source = _read("site/assets/production-v7.js")
    assert "COPY_REPLACEMENTS" not in source
    assert "Generated demo workspace" not in source
    assert "Attendance operations online" not in source
    assert "window.HFData" not in source
    assert 'operationalDataMode !== "integration-required"' in source
    assert "Operational data connection required" in source
    assert "generated browser data as if it were live" in source


def test_production_boundary_hides_legacy_operational_workspace() -> None:
    javascript = _read("site/assets/production-v7.js")
    stylesheet = _read("site/assets/production-v7.css")
    assert 'workspace.setAttribute("inert", "")' in javascript
    assert 'workspace.setAttribute("aria-hidden", "true")' in javascript
    assert ".production-data-blocked #workspace" in stylesheet
    assert "pointer-events: none" in stylesheet
    assert "prefers-reduced-motion: reduce" in stylesheet


def test_checked_in_runtime_config_is_nonproduction_demo_only() -> None:
    source = _read("site/assets/runtime-config.js")
    assert 'environment: "development"' in source
    assert 'operationalDataMode: "demo"' in source
