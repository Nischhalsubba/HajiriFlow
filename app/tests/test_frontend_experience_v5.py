import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent
INDEX = (APP_ROOT / "site" / "index.html").read_text(encoding="utf-8")
CSS = (APP_ROOT / "site" / "assets" / "experience-v5.css").read_text(encoding="utf-8")
LOADING = (APP_ROOT / "site" / "assets" / "loading-v5.js").read_text(encoding="utf-8")
MEDIA = (APP_ROOT / "site" / "assets" / "media-v5.js").read_text(encoding="utf-8")
MOTION = (APP_ROOT / "site" / "assets" / "motion-v5.js").read_text(encoding="utf-8")
NETLIFY = (REPOSITORY_ROOT / "netlify.toml").read_text(encoding="utf-8")


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
    body_classes = re.search(r'<body\s+class="([^"]+)"', INDEX)
    assert body_classes is not None
    assert "app-is-loading" in body_classes.group(1).split()
    assert "showLoading" in LOADING
    assert "finishLoading" in LOADING
    assert "MutationObserver" in LOADING
    assert 'workspace.setAttribute("aria-busy", "false")' in LOADING
    assert ".app-is-loading #workspace" in CSS
    assert "hajiriflow-shimmer" in CSS


def test_people_media_uses_free_licensed_photographic_portraits() -> None:
    assert "https://images.unsplash.com/" in MEDIA
    assert "PORTRAIT_IDS" in MEDIA
    assert 'image.loading = element.matches' in MEDIA
    assert 'image.decoding = "async"' in MEDIA
    assert "is-error" in MEDIA
    assert ".open-avatar" in CSS


def test_photographic_portrait_retry_and_photo_storage_are_valid() -> None:
    assert 'portraitUrl(name, 11)' in MEDIA
    assert "let attempt = 0" in MEDIA
    assert "hajiriflow_employee_photos_v1" in MEDIA
    assert "api.dicebear.com" not in MEDIA
    assert "20260803-7" in INDEX


def test_motion_is_version_pinned_and_reduced_motion_safe() -> None:
    assert "https://cdn.jsdelivr.net/npm/motion@12.42.1/dist/motion.js" in INDEX
    assert "window.Motion" in MOTION
    assert "animate" in MOTION
    assert "stagger" in MOTION
    assert "prefers-reduced-motion: reduce" in MOTION
    assert "prefers-reduced-motion: reduce" in CSS


def test_external_origins_are_limited_by_csp() -> None:
    assert "img-src 'self' data: https://images.unsplash.com" in NETLIFY
    assert "script-src 'self' https://cdn.jsdelivr.net" in NETLIFY
    assert "unsafe-inline" not in NETLIFY
    assert "unsafe-eval" not in NETLIFY
