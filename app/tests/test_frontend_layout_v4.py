from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "assets" / "hajiriflow-v4.css").read_text(encoding="utf-8")
SHELL = (ROOT / "site" / "assets" / "shell-v4.js").read_text(encoding="utf-8")


def test_v4_layout_assets_are_loaded() -> None:
    assert "hajiriflow-v4.css" in INDEX
    assert "shell-v4.js" in INDEX


def test_typography_uses_readable_scale() -> None:
    assert "font-size: 16px" in CSS
    assert ".person-cell strong" in CSS
    assert "font-size: 0.875rem" in CSS
    assert "min-height: 42px" in CSS


def test_workspace_is_fluid_and_sidebar_can_collapse() -> None:
    assert "max-width: none" in CSS
    assert ".sidebar-is-collapsed .sidebar" in CSS
    assert "--v4-sidebar-collapsed" in CSS
    assert "margin-left: var(--v4-sidebar-collapsed)" in CSS


def test_responsive_navigation_is_explicit() -> None:
    assert "(max-width: 1100px)" in CSS
    assert "(max-width: 820px)" in CSS
    assert "(max-width: 560px)" in CSS
    assert "sidebar-is-open" in CSS
    assert "nav-lock" in CSS


def test_hamburger_controls_desktop_and_mobile_navigation() -> None:
    assert 'matchMedia("(min-width: 1101px)")' in SHELL
    assert "sidebar-is-collapsed" in SHELL
    assert "sidebar-is-open" in SHELL
    assert "stopImmediatePropagation" in SHELL
    assert 'setAttribute("aria-expanded"' in SHELL
    assert "localStorage" in SHELL
