from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import RequestIdentity, get_db, require_permission
from hajiriflow.db.models.identity import AuditEvent

router = APIRouter(prefix="/api/v1/admin/audit-events", tags=["audit"])


class AuditEventView(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    object_type: str
    object_id: str | None
    reason: str | None
    before_data: dict
    after_data: dict
    context_data: dict
    request_id: str | None
    occurred_at: datetime


def _view(item: AuditEvent) -> AuditEventView:
    return AuditEventView(
        id=item.id,
        actor_user_id=item.actor_user_id,
        action=item.action,
        object_type=item.object_type,
        object_id=item.object_id,
        reason=item.reason,
        before_data=item.before_data or {},
        after_data=item.after_data or {},
        context_data=item.context_data or {},
        request_id=item.request_id,
        occurred_at=item.occurred_at,
    )


def _escaped_prefix(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[AuditEventView])
def list_audit_events(
    _: Annotated[RequestIdentity, Depends(require_permission("identity.audit.read"))],
    session: Annotated[Session, Depends(get_db)],
    action: Annotated[str | None, Query(max_length=200)] = None,
    action_prefix: Annotated[str | None, Query(max_length=200)] = None,
    object_type: Annotated[str | None, Query(max_length=120)] = None,
    object_id: Annotated[str | None, Query(max_length=240)] = None,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    request_id: Annotated[str | None, Query(max_length=100)] = None,
    organization_id: Annotated[UUID | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query()] = None,
    occurred_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[AuditEventView]:
    query = select(AuditEvent)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    if action_prefix is not None:
        prefix = _escaped_prefix(action_prefix)
        query = query.where(AuditEvent.action.like(f"{prefix}%", escape="\\"))
    if object_type is not None:
        query = query.where(AuditEvent.object_type == object_type)
    if object_id is not None:
        query = query.where(AuditEvent.object_id == object_id)
    if actor_user_id is not None:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if request_id is not None:
        query = query.where(AuditEvent.request_id == request_id)
    if organization_id is not None:
        query = query.where(
            AuditEvent.context_data["organization_id"].as_string()
            == str(organization_id)
        )
    if occurred_from is not None:
        query = query.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(AuditEvent.occurred_at <= occurred_to)
    rows = session.scalars(
        query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_view(row) for row in rows]
