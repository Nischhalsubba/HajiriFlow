from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "assets" / "experience-v5.css").read_text(encoding="utf-8")
LOADING = (ROOT / "site" / "assets" / "loading-v5.js").read_text(encoding="utf-8")
MEDIA = (ROOT / "site" / "assets" / "media-v5.js").read_text(encoding="utf-8")
MOTION = (ROOT / "site" / "assets" / "motion-v5.js").read_text(encoding="utf-8")
NETLIFY = (ROOT / "netlify.toml").read_text(encoding="utf-8")


def test_v5_experience_assets_are_declared() -> None:
    for asset in (
        "experience-v5.css",
        "loading-v5.js",
        "media-v5.js",
        "motion-v5.js",
    ):
        assert f"/assets/{asset}" in INDEX


def test_skeleton_loading_has_real_lifecycle_and_accessibility() -> None:
    assert 'id="app-skeleton"' in INDEX
    assert 'aria-busy="true"' in INDEX
    assert 'class="app-is-loading"' in INDEX
    assert "showLoading" in LOADING
    assert "finishLoading" in LOADING
    assert "MutationObserver" in LOADING
    assert 'workspace.setAttribute("aria-busy", "false")' in LOADING
    assert ".app-is-loading #workspace" in CSS
    assert "hajiriflow-shimmer" in CSS


def test_people_media_uses_open_licensed_deterministic_avatars() -> None:
    assert "https://api.dicebear.com/10.x/notionists-neutral/svg" in MEDIA
    assert "URLSearchParams" in MEDIA
    assert 'image.loading = element.matches' in MEDIA
    assert 'image.decoding = "async"' in MEDIA
    assert "is-error" in MEDIA
    assert ".open-avatar" in CSS


def test_motion_is_version_pinned_and_reduced_motion_safe() -> None:
    assert "https://cdn.jsdelivr.net/npm/motion@12.42.1/+esm" in MOTION
    assert "animate" in MOTION
    assert "stagger" in MOTION
    assert "prefers-reduced-motion: reduce" in MOTION
    assert "prefers-reduced-motion: reduce" in CSS


def test_external_origins_are_limited_by_csp() -> None:
    assert "img-src 'self' data: https://api.dicebear.com" in NETLIFY
    assert "script-src 'self' https://cdn.jsdelivr.net" in NETLIFY
    assert "unsafe-inline" not in NETLIFY
    assert "unsafe-eval" not in NETLIFY
