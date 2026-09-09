from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_permission,
)
from hajiriflow.core.config import Settings, get_settings
from hajiriflow.db.models.identity import UserAccount
from hajiriflow.identity.admin import IdentityAdminService
from hajiriflow.identity.exceptions import DuplicateUsername

router = APIRouter(prefix="/api/v1/admin", tags=["identity-admin"])


class AccountUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    employee_id: UUID | None = None


class AccountView(BaseModel):
    id: UUID
    username: str
    display_name: str
    status: str
    must_change_password: bool
    employee_id: UUID | None


class EmployeeLinkView(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    employee_code: str
    display_name: str
    status: str


def _account(item: UserAccount) -> AccountView:
    return AccountView(
        id=item.id,
        username=item.username,
        display_name=item.display_name,
        status=item.status,
        must_change_password=item.must_change_password,
        employee_id=item.employee_id,
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateUsername):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/users/search", response_model=list[AccountView])
def search_users(
    _: Annotated[RequestIdentity, Depends(require_permission("identity.user.read"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    account_status: Annotated[str | None, Query(alias="status")] = None,
    linked: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[AccountView]:
    try:
        rows = IdentityAdminService(session, settings).search_users(
            query=q,
            status=account_status,
            linked=linked,
            limit=limit,
            offset=offset,
        )
        return [_account(row) for row in rows]
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/employee-links", response_model=list[EmployeeLinkView])
def search_employee_links(
    _: Annotated[RequestIdentity, Depends(require_permission("identity.user.manage"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    organization_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[EmployeeLinkView]:
    rows = IdentityAdminService(session, settings).search_employee_links(
        query=q,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return [
        EmployeeLinkView(
            id=employee.id,
            organization_id=employee.organization_id,
            organization_name=organization.display_name,
            employee_code=employee.employee_code,
            display_name=employee.display_name,
            status=employee.status,
        )
        for employee, organization in rows
    ]


@router.patch("/users/{user_id}", response_model=AccountView)
def update_user(
    user_id: UUID,
    payload: AccountUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_permission("identity.user.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountView:
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="at least one account field is required")
    try:
        item = IdentityAdminService(session, settings).update_user(
            user_id=user_id,
            actor_user_id=identity.principal.user.id,
            username=payload.username if "username" in payload.model_fields_set else None,
            display_name=(
                payload.display_name if "display_name" in payload.model_fields_set else None
            ),
            employee_id=payload.employee_id,
            employee_id_supplied="employee_id" in payload.model_fields_set,
        )
        return _account(item)
    except (LookupError, ValueError, DuplicateUsername) as exc:
        raise _error(exc) from exc
