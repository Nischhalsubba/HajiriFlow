import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hajiriflow import __version__
from hajiriflow.api.attendance import router as attendance_router
from hajiriflow.api.attendance_baseline import router as attendance_baseline_router
from hajiriflow.api.audit import router as audit_router
from hajiriflow.api.biometric import router as biometric_router
from hajiriflow.api.calendar_leave import router as calendar_leave_router
from hajiriflow.api.calendar_leave_baseline import router as calendar_leave_baseline_router
from hajiriflow.api.csrf import router as csrf_router
from hajiriflow.api.device import router as device_router
from hajiriflow.api.device_baseline import router as device_baseline_router
from hajiriflow.api.device_identity import router as device_identity_router
from hajiriflow.api.device_inventory import router as device_inventory_router
from hajiriflow.api.health import router as health_router
from hajiriflow.api.identity import router as identity_router
from hajiriflow.api.identity_admin_baseline import router as identity_admin_baseline_router
from hajiriflow.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from hajiriflow.api.operations import router as operations_router
from hajiriflow.api.payroll import router as payroll_router
from hajiriflow.api.payroll_baseline import router as payroll_baseline_router
from hajiriflow.api.reporting import router as reporting_router
from hajiriflow.api.role_lifecycle import router as role_lifecycle_router
from hajiriflow.api.workforce import router as workforce_router
from hajiriflow.api.workforce_management import router as workforce_management_router
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
    app.include_router(identity_admin_baseline_router)
    app.include_router(audit_router)
    app.include_router(role_lifecycle_router)
    app.include_router(workforce_router)
    app.include_router(workforce_management_router)
    app.include_router(calendar_leave_router)
    app.include_router(calendar_leave_baseline_router)
    app.include_router(attendance_router)
    app.include_router(attendance_baseline_router)
    app.include_router(payroll_router)
    app.include_router(payroll_baseline_router)
    app.include_router(device_router)
    app.include_router(device_baseline_router)
    app.include_router(device_inventory_router)
    app.include_router(device_identity_router)
    app.include_router(reporting_router)
    app.include_router(operations_router)
    app.include_router(biometric_router)
    app.include_router(csrf_router)
    return app


app = create_app()
