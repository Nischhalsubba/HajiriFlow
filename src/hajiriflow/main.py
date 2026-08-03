from fastapi import FastAPI

from hajiriflow import __version__
from hajiriflow.api.health import router as health_router
from hajiriflow.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="HajiriFlow API",
        description="Attendance to payroll, with every record accounted for.",
        version=__version__,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.include_router(health_router)
    return app


app = create_app()
