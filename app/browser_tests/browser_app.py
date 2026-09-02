from pathlib import Path

from fastapi.staticfiles import StaticFiles

from hajiriflow.main import create_app

SITE_ROOT = Path(__file__).resolve().parents[1] / "site"

app = create_app()
# Test-only same-origin browser harness. API routes are registered before the
# root mount, so /api/v1/* remains the real FastAPI identity implementation.
app.mount("/", StaticFiles(directory=SITE_ROOT, html=True), name="browser-test-site")
