from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hajiriflow import __version__
from hajiriflow.api.csrf import router as csrf_router
from hajiriflow.api.health import router as health_router
from hajiriflow.api.identity import router as identity_router
from hajiriflow.api.middleware import SecurityHeadersMiddleware
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
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(csrf_router)
    return app


app = create_app()
