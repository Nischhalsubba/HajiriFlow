import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hajiriflow import __version__
from hajiriflow.api.calendar_leave import router as calendar_leave_router
from hajiriflow.api.csrf import router as csrf_router
from hajiriflow.api.health import router as health_router
from hajiriflow.api.identity import router as identity_router
from hajiriflow.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from hajiriflow.api.role_lifecycle import router as role_lifecycle_router
from hajiriflow.api.workforce import router as workforce_router
from hajiriflow.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    request_log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger("hajiriflow.request").setLevel(request_log_level)

    app = FastAPI(
        title="HajiriFlow API",
        description="Attendance to payroll, with every record accounted for.",
        version=__version__,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        protected_environment=settings.environment in {"staging", "production"},
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(role_lifecycle_router)
    app.include_router(workforce_router)
    app.include_router(calendar_leave_router)
    app.include_router(csrf_router)
    return app


app = create_app()
