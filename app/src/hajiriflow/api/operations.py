from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_organization_permission,
)
from hajiriflow.operations.service import OperationalDashboardService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/operations",
    tags=["operations"],
)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/dashboard")
def operational_dashboard(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("operations.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    work_date: Annotated[date | None, Query()] = None,
    stale_after_minutes: Annotated[int, Query(ge=5, le=1440)] = 30,
) -> dict:
    try:
        return OperationalDashboardService(session).snapshot(
            organization_id=organization_id,
            work_date=work_date,
            stale_after_minutes=stale_after_minutes,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/metrics")
def operational_metrics(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("operations.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    stale_after_minutes: Annotated[int, Query(ge=5, le=1440)] = 30,
) -> dict:
    """Return the same sanitized aggregate contract for monitoring collectors."""
    try:
        snapshot = OperationalDashboardService(session).snapshot(
            organization_id=organization_id,
            stale_after_minutes=stale_after_minutes,
        )
        return {
            "generated_at": snapshot["generated_at"],
            "devices": snapshot["devices"],
            "pulls_24h": {
                key: value
                for key, value in snapshot["pulls_24h"].items()
                if key != "recent_failures"
            },
            "jobs_24h": snapshot["jobs_24h"],
            "attendance": snapshot["attendance"],
            "payroll": snapshot["payroll"],
            "alerts": snapshot["alerts"],
        }
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
