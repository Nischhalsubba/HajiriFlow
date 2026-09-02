from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import RequestIdentity, get_db, require_csrf, require_permission
from hajiriflow.core.config import Settings, get_settings
from hajiriflow.identity.permissions import FULL_ACCESS, ScopeType, has_permission
from hajiriflow.identity.role_lifecycle import ActiveRoleAssignment, RoleLifecycleService

router = APIRouter(prefix="/api/v1/admin", tags=["identity-administration"])


class RoleView(BaseModel):
    code: str
    name: str
    description: str | None


class RoleAssignmentView(BaseModel):
    id: UUID
    user_id: UUID
    role_code: str
    role_name: str
    scope_type: ScopeType
    scope_id: UUID | None
    starts_at: datetime
    assigned_by: UUID | None


def assignment_view(record: ActiveRoleAssignment) -> RoleAssignmentView:
    return RoleAssignmentView(
        id=record.id,
        user_id=record.user_id,
        role_code=record.role_code,
        role_name=record.role_name,
        scope_type=ScopeType(record.scope_type),
        scope_id=record.scope_id,
        starts_at=record.starts_at,
        assigned_by=record.assigned_by,
    )


@router.get("/roles", response_model=list[RoleView])
def list_roles(
    _: Annotated[RequestIdentity, Depends(require_permission("identity.user.read"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[RoleView]:
    roles = RoleLifecycleService(session, settings).list_roles()
    return [
        RoleView(code=role.code, name=role.name, description=role.description)
        for role in roles
    ]


@router.get("/role-assignments", response_model=list[RoleAssignmentView])
def list_role_assignments(
    _: Annotated[RequestIdentity, Depends(require_permission("identity.user.read"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[RoleAssignmentView]:
    records = RoleLifecycleService(session, settings).list_active_assignments()
    return [assignment_view(record) for record in records]


@router.delete("/role-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_role_assignment(
    assignment_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[RequestIdentity, Depends(require_permission("identity.role.assign"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    service = RoleLifecycleService(session, settings)
    try:
        record = service.get_active_assignment(assignment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="active role assignment not found") from exc

    if record.user_id == identity.principal.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="you cannot revoke your own active role assignment",
        )
    if record.role_code == "system_administrator" and not has_permission(
        identity.principal.grants,
        FULL_ACCESS,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="system administrator role requires system administrator access",
        )

    try:
        service.revoke_assignment(
            assignment_id,
            actor_user_id=identity.principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="active role assignment not found") from exc
