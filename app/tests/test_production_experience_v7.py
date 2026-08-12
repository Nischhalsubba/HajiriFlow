from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent
INDEX = (APP_ROOT / "site" / "index.html").read_text(encoding="utf-8")
MEDIA = (APP_ROOT / "site" / "assets" / "media-v5.js").read_text(encoding="utf-8")
PRODUCTION = (APP_ROOT / "site" / "assets" / "production-v7.js").read_text(encoding="utf-8")
CSS = (APP_ROOT / "site" / "assets" / "production-v7.css").read_text(encoding="utf-8")
NETLIFY = (REPOSITORY_ROOT / "netlify.toml").read_text(encoding="utf-8")


def test_production_assets_are_loaded_after_core_application() -> None:
    assert "/assets/production-v7.css" in INDEX
    assert "/assets/production-v7.js" in INDEX
    assert INDEX.index("app-v3.js") < INDEX.index("production-v7.js")


def test_employee_portraits_use_free_licensed_photographic_source() -> None:
    assert "https://images.unsplash.com/" in MEDIA
    assert "PORTRAIT_IDS" in MEDIA
    assert "api.dicebear.com" not in MEDIA
    assert "is-photographic" in MEDIA
    assert "object-position" in CSS


def test_employee_photo_upload_has_validation_and_persistence() -> None:
    assert "image/jpeg,image/png,image/webp" in PRODUCTION
    assert "MAX_PHOTO_BYTES" in PRODUCTION
    assert "canvas.toDataURL" in PRODUCTION
    assert "HFMedia?.setPhoto" in PRODUCTION
    assert "HFMedia?.removePhoto" in PRODUCTION
    assert "hajiriflow_employee_photos_v1" in MEDIA


def test_demo_language_and_destructive_demo_controls_are_removed() -> None:
    assert '"HajiriFlow Demo", "HajiriFlow"' in PRODUCTION
    assert '"Live demo workspace", "Workforce operations"' in PRODUCTION
    assert 'new Set(["regenerate-demo", "confirm-regenerate"])' in PRODUCTION
    assert "provider-card.muted" in PRODUCTION


def test_csp_allows_only_required_portrait_origin() -> None:
    assert 'base = "app"' in NETLIFY
    assert "https://images.unsplash.com" in NETLIFY
    assert "https://api.dicebear.com" not in NETLIFY
    assert "unsafe-inline" not in NETLIFY
    assert "unsafe-eval" not in NETLIFY
