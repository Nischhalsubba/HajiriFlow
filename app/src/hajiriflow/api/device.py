from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.db.models.device import (
    Device,
    DeviceCredential,
    DeviceEmployeeMapping,
    DevicePullSession,
    DeviceUser,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import Employee
from hajiriflow.device_platform.service import DevicePlatformService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/devices",
    tags=["devices"],
)


class DeviceCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    vendor: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=160)
    adapter_key: str = Field(min_length=1, max_length=120)
    endpoint_uri: str = Field(min_length=1, max_length=500)
    capabilities: dict = Field(default_factory=dict)
    pull_interval_seconds: int = Field(default=300, ge=60, le=86400)


class DeviceStatusUpdate(BaseModel):
    status: Literal["active", "disabled", "error"]


class DeviceView(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    vendor: str
    model: str | None
    serial_number: str | None
    adapter_key: str
    endpoint_uri: str
    capabilities: dict
    status: str
    pull_interval_seconds: int
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CredentialMetadataView(BaseModel):
    id: UUID
    device_id: UUID
    version: int
    key_id: str
    created_by: UUID | None
    created_at: datetime
    retired_at: datetime | None


class PullSessionView(BaseModel):
    id: UUID
    device_id: UUID
    mode: str
    status: str
    attempt_count: int
    ingested_count: int
    duplicate_count: int
    error_code: str | None
    error_detail: str | None
    started_at: datetime
    ended_at: datetime | None


class DeviceUserView(BaseModel):
    id: UUID
    device_id: UUID
    external_user_id: str
    display_name: str | None
    privilege: str | None
    active: bool
    template_count: int
    first_seen_at: datetime
    last_seen_at: datetime


class DeviceMappingCreate(BaseModel):
    device_user_id: UUID
    employee_id: UUID


class DeviceMappingView(BaseModel):
    id: UUID
    device_user_id: UUID
    employee_id: UUID
    status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


def _device_view(item: Device) -> DeviceView:
    return DeviceView(
        id=item.id,
        organization_id=item.organization_id,
        code=item.code,
        name=item.name,
        vendor=item.vendor,
        model=item.model,
        serial_number=item.serial_number,
        adapter_key=item.adapter_key,
        endpoint_uri=item.endpoint_uri,
        capabilities=item.capabilities,
        status=item.status,
        pull_interval_seconds=item.pull_interval_seconds,
        last_seen_at=item.last_seen_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _load_device(session: Session, organization_id: UUID, device_id: UUID) -> Device:
    item = session.get(Device, device_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    return item


@router.get("", response_model=list[DeviceView])
def list_devices(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeviceView]:
    items = session.scalars(
        select(Device)
        .where(Device.organization_id == organization_id)
        .order_by(Device.code)
    ).all()
    return [_device_view(item) for item in items]


@router.post("", response_model=DeviceView, status_code=status.HTTP_201_CREATED)
def create_device(
    organization_id: UUID,
    payload: DeviceCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceView:
    item = Device(
        organization_id=organization_id,
        code=payload.code.strip(),
        name=payload.name.strip(),
        vendor=payload.vendor.strip(),
        model=payload.model.strip() if payload.model else None,
        serial_number=payload.serial_number.strip() if payload.serial_number else None,
        adapter_key=payload.adapter_key.strip(),
        endpoint_uri=payload.endpoint_uri.strip(),
        capabilities=payload.capabilities,
        pull_interval_seconds=payload.pull_interval_seconds,
    )
    session.add(item)
    session.flush()
    session.add(
        AuditEvent(
            actor_user_id=identity.principal.user.id,
            action="device.register",
            object_type="device",
            object_id=str(item.id),
            after_data={
                "code": item.code,
                "adapter_key": item.adapter_key,
                "status": item.status,
                "pull_interval_seconds": item.pull_interval_seconds,
            },
            context_data={
                "organization_id": str(organization_id),
                "source": "device_api",
            },
        )
    )
    session.commit()
    return _device_view(item)


@router.patch("/{device_id}/status", response_model=DeviceView)
def update_device_status(
    organization_id: UUID,
    device_id: UUID,
    payload: DeviceStatusUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceView:
    item = _load_device(session, organization_id, device_id)
    before = item.status
    item.status = payload.status
    session.add(
        AuditEvent(
            actor_user_id=identity.principal.user.id,
            action="device.status.update",
            object_type="device",
            object_id=str(item.id),
            before_data={"status": before},
            after_data={"status": item.status},
            context_data={
                "organization_id": str(organization_id),
                "source": "device_api",
            },
        )
    )
    session.commit()
    return _device_view(item)


@router.get("/{device_id}/credentials", response_model=list[CredentialMetadataView])
def credential_metadata(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[CredentialMetadataView]:
    _load_device(session, organization_id, device_id)
    items = session.scalars(
        select(DeviceCredential)
        .where(
            DeviceCredential.organization_id == organization_id,
            DeviceCredential.device_id == device_id,
        )
        .order_by(DeviceCredential.version.desc())
    ).all()
    return [
        CredentialMetadataView(
            id=item.id,
            device_id=item.device_id,
            version=item.version,
            key_id=item.key_id,
            created_by=item.created_by,
            created_at=item.created_at,
            retired_at=item.retired_at,
        )
        for item in items
    ]


@router.get("/{device_id}/pulls", response_model=list[PullSessionView])
def pull_history(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PullSessionView]:
    _load_device(session, organization_id, device_id)
    items = session.scalars(
        select(DevicePullSession)
        .where(
            DevicePullSession.organization_id == organization_id,
            DevicePullSession.device_id == device_id,
        )
        .order_by(DevicePullSession.started_at.desc())
        .limit(100)
    ).all()
    return [
        PullSessionView(
            id=item.id,
            device_id=item.device_id,
            mode=item.mode,
            status=item.status,
            attempt_count=item.attempt_count,
            ingested_count=item.ingested_count,
            duplicate_count=item.duplicate_count,
            error_code=item.error_code,
            error_detail=item.error_detail,
            started_at=item.started_at,
            ended_at=item.ended_at,
        )
        for item in items
    ]


@router.get("/{device_id}/users", response_model=list[DeviceUserView])
def list_device_users(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeviceUserView]:
    _load_device(session, organization_id, device_id)
    items = session.scalars(
        select(DeviceUser)
        .where(
            DeviceUser.organization_id == organization_id,
            DeviceUser.device_id == device_id,
        )
        .order_by(DeviceUser.external_user_id)
    ).all()
    return [
        DeviceUserView(
            id=item.id,
            device_id=item.device_id,
            external_user_id=item.external_user_id,
            display_name=item.display_name,
            privilege=item.privilege,
            active=item.active,
            template_count=item.template_count,
            first_seen_at=item.first_seen_at,
            last_seen_at=item.last_seen_at,
        )
        for item in items
    ]


@router.post(
    "/mappings",
    response_model=DeviceMappingView,
    status_code=status.HTTP_201_CREATED,
)
def map_device_user(
    organization_id: UUID,
    payload: DeviceMappingCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.mapping.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceMappingView:
    device_user = session.get(DeviceUser, payload.device_user_id)
    employee = session.get(Employee, payload.employee_id)
    if not device_user or device_user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device user not found")
    if not employee or employee.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee not found")
    try:
        item = DevicePlatformService(session).map_device_user(
            device_user=device_user,
            employee=employee,
            actor_user_id=identity.principal.user.id,
        )
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DeviceMappingView(
        id=item.id,
        device_user_id=item.device_user_id,
        employee_id=item.employee_id,
        status=item.status,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/mappings/all", response_model=list[DeviceMappingView])
def list_mappings(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeviceMappingView]:
    items = session.scalars(
        select(DeviceEmployeeMapping)
        .where(DeviceEmployeeMapping.organization_id == organization_id)
        .order_by(DeviceEmployeeMapping.updated_at.desc())
    ).all()
    return [
        DeviceMappingView(
            id=item.id,
            device_user_id=item.device_user_id,
            employee_id=item.employee_id,
            status=item.status,
            created_by=item.created_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]
