from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADING = (ROOT / "site" / "assets" / "loading-v5.js").read_text(encoding="utf-8")
PRODUCTION = (ROOT / "site" / "assets" / "production-v7.js").read_text(encoding="utf-8")


def test_loading_guard_prevents_recursive_document_title_mutations() -> None:
    assert "installIdempotentTitleGuard" in LOADING
    assert 'Object.getOwnPropertyDescriptor(prototype, "title")' in LOADING
    assert "descriptor.get.call(document) !== nextTitle" in LOADING
    assert LOADING.index("installIdempotentTitleGuard();") < LOADING.index("new MutationObserver")
    assert 'document.title = "HajiriFlow | Workforce Operations"' in PRODUCTION


def test_loading_state_has_timeout_and_user_recovery() -> None:
    assert "STARTUP_FAILURE_MS" in LOADING
    assert "scheduleFailureFallback" in LOADING
    assert "showFailure" in LOADING
    assert 'button.textContent = "Reload HajiriFlow"' in LOADING
    assert 'window.addEventListener("error"' in LOADING
    assert 'window.addEventListener("unhandledrejection"' in LOADING
    assert "finishLoading(true)" in LOADING
