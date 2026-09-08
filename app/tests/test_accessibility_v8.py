from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
INDEX = (APP_ROOT / "site" / "index.html").read_text(encoding="utf-8")
CSS = (APP_ROOT / "site" / "assets" / "accessibility-v8.css").read_text(
    encoding="utf-8"
)
JS = (APP_ROOT / "site" / "assets" / "accessibility-v8.js").read_text(
    encoding="utf-8"
)


def test_accessibility_assets_load_last_in_the_interaction_stack() -> None:
    assert "/assets/accessibility-v8.css" in INDEX
    assert "/assets/accessibility-v8.js" in INDEX
    assert INDEX.index("production-v7.css") < INDEX.index("accessibility-v8.css")
    assert INDEX.index("motion-v5.js") < INDEX.index("accessibility-v8.js")


def test_focus_not_obscured_and_visible_focus_contract() -> None:
    assert "scroll-padding-top" in CSS
    assert "scroll-margin-block" in CSS
    assert ":focus-visible" in CSS
    assert "outline: 3px solid" in CSS
    assert "outline-offset: 3px" in CSS
    assert "forced-colors: active" in CSS


def test_interactive_targets_exceed_wcag_22_minimum() -> None:
    assert "min-block-size: 44px" in CSS
    assert "min-block-size: 40px" in CSS
    assert ".table-action" in CSS
    assert ".text-action" in CSS


def test_reduced_motion_suppresses_nonessential_animation_and_scroll() -> None:
    assert "prefers-reduced-motion: reduce" in CSS
    assert "animation-duration: .01ms !important" in CSS
    assert "animation-iteration-count: 1 !important" in CSS
    assert "transition-duration: .01ms !important" in CSS
    assert "scroll-behavior: auto !important" in CSS


def test_wide_tables_are_keyboard_scroll_regions_with_headers() -> None:
    assert 'root.querySelectorAll(".table-scroll, .table-wrap")' in JS
    assert 'container.tabIndex = 0' in JS
    assert 'container.setAttribute("role", "region")' in JS
    assert 'container.setAttribute("aria-label", tableLabel(container))' in JS
    assert 'header.setAttribute("scope", "col")' in JS
    assert 'header.setAttribute("aria-label", "Actions")' in JS


def test_dialogs_trap_tab_and_restore_focus() -> None:
    assert 'event.key !== "Tab"' in JS
    assert "event.shiftKey" in JS
    assert "last.focus()" in JS
    assert "first.focus()" in JS
    assert "restoreOutsideFocus" in JS
    assert "lastOutsideFocus.focus" in JS
    assert 'event.key === "Escape"' in JS


def test_command_dialog_has_an_accessible_name() -> None:
    assert 'aria-labelledby="command-title"' in INDEX
    assert 'id="command-title">Search and commands</h2>' in INDEX
    assert 'aria-label="Search employees, pages, or actions"' in INDEX


def test_production_skip_link_moves_to_visible_status_surface() -> None:
    assert 'document.getElementById("production-data-boundary")' in JS
    assert 'skipLink.setAttribute("href", "#production-data-boundary")' in JS
    assert 'skipLink.textContent = "Skip to production status"' in JS
    assert "boundary.tabIndex = -1" in JS
