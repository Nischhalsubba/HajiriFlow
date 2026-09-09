from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.db.models.device_identity import DeviceArchive, DeviceIdentityAction
from hajiriflow.device_platform.identity_lifecycle import DeviceIdentityLifecycleService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/device-identities",
    tags=["device-identities"],
)


class IdentityActionPreviewRequest(BaseModel):
    action_type: Literal[
        "push_users",
        "migrate_users",
        "archive_export",
        "archive_restore",
    ]
    source_device_id: UUID | None = None
    target_device_id: UUID | None = None
    employee_ids: list[UUID] = Field(default_factory=list, max_length=200)
    device_user_ids: list[UUID] = Field(default_factory=list, max_length=200)
    archive_id: UUID | None = None


class IdentityActionApproval(BaseModel):
    preview_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class IdentityActionView(BaseModel):
    id: UUID
    action_type: str
    status: str
    source_device_id: UUID | None
    target_device_id: UUID | None
    preview_data: dict
    preview_hash: str
    result_data: dict
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    approved_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None


class DeviceArchiveView(BaseModel):
    id: UUID
    source_device_id: UUID
    manifest_data: dict
    status: str
    created_at: datetime
    last_restored_at: datetime | None


def action_view(item: DeviceIdentityAction) -> IdentityActionView:
    return IdentityActionView(
        id=item.id,
        action_type=item.action_type,
        status=item.status,
        source_device_id=item.source_device_id,
        target_device_id=item.target_device_id,
        preview_data=item.preview_data,
        preview_hash=item.preview_hash,
        result_data=item.result_data,
        error_code=item.error_code,
        error_detail=item.error_detail,
        created_at=item.created_at,
        approved_at=item.approved_at,
        started_at=item.started_at,
        ended_at=item.ended_at,
    )


def archive_view(item: DeviceArchive) -> DeviceArchiveView:
    return DeviceArchiveView(
        id=item.id,
        source_device_id=item.source_device_id,
        manifest_data=item.manifest_data,
        status=item.status,
        created_at=item.created_at,
        last_restored_at=item.last_restored_at,
    )


def service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/compare/{device_id}")
def compare_device_identities(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return DeviceIdentityLifecycleService(session).compare_device(
            organization_id=organization_id,
            device_id=device_id,
        )
    except LookupError as exc:
        raise service_error(exc) from exc


@router.post(
    "/actions/preview",
    response_model=IdentityActionView,
    status_code=status.HTTP_201_CREATED,
)
def preview_identity_action(
    organization_id: UUID,
    payload: IdentityActionPreviewRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.mapping.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> IdentityActionView:
    try:
        item = DeviceIdentityLifecycleService(session).preview_action(
            organization_id=organization_id,
            action_type=payload.action_type,
            requested_by=identity.principal.user.id,
            source_device_id=payload.source_device_id,
            target_device_id=payload.target_device_id,
            employee_ids=payload.employee_ids,
            device_user_ids=payload.device_user_ids,
            archive_id=payload.archive_id,
        )
        return action_view(item)
    except (LookupError, ValueError) as exc:
        raise service_error(exc) from exc


@router.post("/actions/{action_id}/approve", response_model=IdentityActionView)
def approve_identity_action(
    organization_id: UUID,
    action_id: UUID,
    payload: IdentityActionApproval,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.mapping.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> IdentityActionView:
    try:
        item = DeviceIdentityLifecycleService(session).approve_action(
            organization_id=organization_id,
            action_id=action_id,
            preview_hash=payload.preview_hash,
            approved_by=identity.principal.user.id,
        )
        return action_view(item)
    except (LookupError, ValueError) as exc:
        raise service_error(exc) from exc


@router.post("/actions/{action_id}/cancel", response_model=IdentityActionView)
def cancel_identity_action(
    organization_id: UUID,
    action_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.mapping.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> IdentityActionView:
    try:
        item = DeviceIdentityLifecycleService(session).cancel_action(
            organization_id=organization_id,
            action_id=action_id,
            actor_user_id=identity.principal.user.id,
        )
        return action_view(item)
    except (LookupError, ValueError) as exc:
        raise service_error(exc) from exc


@router.get("/actions/{action_id}", response_model=IdentityActionView)
def get_identity_action(
    organization_id: UUID,
    action_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> IdentityActionView:
    item = session.get(DeviceIdentityAction, action_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="device identity action not found")
    return action_view(item)


@router.get("/actions", response_model=list[IdentityActionView])
def list_identity_actions(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[IdentityActionView]:
    items = session.scalars(
        select(DeviceIdentityAction)
        .where(DeviceIdentityAction.organization_id == organization_id)
        .order_by(DeviceIdentityAction.created_at.desc(), DeviceIdentityAction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [action_view(item) for item in items]


@router.get("/archives", response_model=list[DeviceArchiveView])
def list_device_archives(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DeviceArchiveView]:
    items = session.scalars(
        select(DeviceArchive)
        .where(DeviceArchive.organization_id == organization_id)
        .order_by(DeviceArchive.created_at.desc(), DeviceArchive.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [archive_view(item) for item in items]


@router.get("/archives/{archive_id}", response_model=DeviceArchiveView)
def get_device_archive(
    organization_id: UUID,
    archive_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceArchiveView:
    item = session.get(DeviceArchive, archive_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="device archive not found")
    return archive_view(item)
