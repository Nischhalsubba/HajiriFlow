from datetime import UTC, datetime

from fastapi import APIRouter

from hajiriflow import __version__
from hajiriflow.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "hajiriflow-web",
        "version": __version__,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
def ready() -> dict[str, str]:
    # Database and migration checks will be added when persistence is introduced.
    return {"status": "ready"}
