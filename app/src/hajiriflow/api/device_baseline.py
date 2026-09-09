from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.calendar_leave.bs_dates import BsDateService
from hajiriflow.core.config import Settings, get_settings
from hajiriflow.db.models.device import (
    Device,
    DeviceCredential,
    DeviceEmployeeMapping,
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.device_baseline import DeviceOperation
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.device_platform.operations import DeviceOperationService
from hajiriflow.device_platform.runtime import build_device_secret_cipher
from hajiriflow.device_platform.service import DevicePlatformService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/devices",
    tags=["device-baseline"],
)
NEPAL = ZoneInfo("Asia/Kathmandu")


class DeviceRegistrationUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    vendor: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=160)
    adapter_key: str = Field(min_length=1, max_length=120)
    endpoint_uri: str = Field(min_length=1, max_length=500)
    capabilities: dict = Field(default_factory=dict)
    pull_interval_seconds: int = Field(default=300, ge=60, le=86400)


class DeviceRegistrationView(DeviceRegistrationUpdate):
    id: UUID
    status: str


class RuntimeConfigurationUpdate(BaseModel):
    site: str | None = Field(default=None, max_length=160)
    protocol_preference: Literal["auto", "http", "https"] = "auto"
    timeout_seconds: int = Field(default=10, ge=1, le=120)


class RuntimeConfigurationView(RuntimeConfigurationUpdate):
    device_id: UUID
    last_successful_pull_at: datetime | None
    last_diagnostics_at: datetime | None


class GatewayCredentialUpdate(BaseModel):
    bearer_token: str = Field(min_length=8, max_length=4096)


class CredentialRotationView(BaseModel):
    id: UUID
    device_id: UUID
    version: int
    key_id: str
    created_at: datetime


class HistoricalPullRequest(BaseModel):
    start_at: datetime
    end_at: datetime


class DeviceOperationView(BaseModel):
    id: UUID
    device_id: UUID
    operation_type: str
    status: str
    window_start: datetime | None
    window_end: datetime | None
    result_data: dict
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class UnlinkedPunchView(BaseModel):
    id: UUID
    device_id: UUID
    device_user_identifier: str
    occurred_at: datetime
    nepal_local_datetime: datetime
    nepal_ad_date: str
    bs_date: str
    punch_kind: str
    verification_method: str | None


def _device(session: Session, organization_id: UUID, device_id: UUID) -> Device:
    item = session.get(Device, device_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    return item


def _operation_view(item: DeviceOperation) -> DeviceOperationView:
    return DeviceOperationView(
        id=item.id,
        device_id=item.device_id,
        operation_type=item.operation_type,
        status=item.status,
        window_start=item.window_start,
        window_end=item.window_end,
        result_data=item.result_data,
        error_code=item.error_code,
        error_detail=item.error_detail,
        created_at=item.created_at,
        started_at=item.started_at,
        ended_at=item.ended_at,
    )


def _runtime_view(item) -> RuntimeConfigurationView:
    return RuntimeConfigurationView(
        device_id=item.device_id,
        site=item.site,
        protocol_preference=item.protocol_preference,
        timeout_seconds=item.timeout_seconds,
        last_successful_pull_at=item.last_successful_pull_at,
        last_diagnostics_at=item.last_diagnostics_at,
    )


@router.get("/operations/{operation_id}", response_model=DeviceOperationView)
def get_device_operation(
    organization_id: UUID,
    operation_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceOperationView:
    item = session.get(DeviceOperation, operation_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device operation not found")
    return _operation_view(item)


@router.get("/unlinked-punches", response_model=list[UnlinkedPunchView])
def list_unlinked_punches(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    device_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UnlinkedPunchView]:
    query = select(RawPunch).where(RawPunch.organization_id == organization_id)
    if device_id is not None:
        _device(session, organization_id, device_id)
        query = query.where(RawPunch.device_id == device_id)
    punches = session.scalars(
        query.order_by(RawPunch.occurred_at.desc(), RawPunch.id).offset(offset).limit(limit * 5)
    ).all()
    results: list[UnlinkedPunchView] = []
    for punch in punches:
        device_user = session.scalar(
            select(DeviceUser).where(
                DeviceUser.device_id == punch.device_id,
                DeviceUser.external_user_id == punch.device_user_identifier,
            )
        )
        mapping = None
        if device_user is not None:
            mapping = session.scalar(
                select(DeviceEmployeeMapping.id).where(
                    DeviceEmployeeMapping.device_user_id == device_user.id,
                    DeviceEmployeeMapping.status == "active",
                )
            )
        if mapping is not None:
            continue
        observed = punch.occurred_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=NEPAL)
        local = observed.astimezone(NEPAL)
        results.append(
            UnlinkedPunchView(
                id=punch.id,
                device_id=punch.device_id,
                device_user_identifier=punch.device_user_identifier,
                occurred_at=punch.occurred_at,
                nepal_local_datetime=local,
                nepal_ad_date=local.date().isoformat(),
                bs_date=BsDateService.ad_to_bs(local.date()),
                punch_kind=punch.punch_kind,
                verification_method=punch.verification_method,
            )
        )
        if len(results) >= limit:
            break
    return results


@router.put("/{device_id}/registration", response_model=DeviceRegistrationView)
def update_device_registration(
    organization_id: UUID,
    device_id: UUID,
    payload: DeviceRegistrationUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceRegistrationView:
    item = _device(session, organization_id, device_id)
    before = {
        "code": item.code,
        "name": item.name,
        "vendor": item.vendor,
        "adapter_key": item.adapter_key,
        "endpoint_uri": item.endpoint_uri,
        "pull_interval_seconds": item.pull_interval_seconds,
    }
    item.code = payload.code.strip()
    item.name = payload.name.strip()
    item.vendor = payload.vendor.strip()
    item.model = payload.model.strip() if payload.model else None
    item.serial_number = payload.serial_number.strip() if payload.serial_number else None
    item.adapter_key = payload.adapter_key.strip()
    item.endpoint_uri = payload.endpoint_uri.strip()
    item.capabilities = payload.capabilities
    item.pull_interval_seconds = payload.pull_interval_seconds
    session.add(
        AuditEvent(
            actor_user_id=identity.principal.user.id,
            action="device.registration.update",
            object_type="device",
            object_id=str(device_id),
            before_data=before,
            after_data={
                "code": item.code,
                "name": item.name,
                "vendor": item.vendor,
                "adapter_key": item.adapter_key,
                "endpoint_uri": item.endpoint_uri,
                "pull_interval_seconds": item.pull_interval_seconds,
            },
            context_data={"organization_id": str(organization_id)},
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="device code or serial number already exists") from exc
    return DeviceRegistrationView(
        id=item.id,
        status=item.status,
        code=item.code,
        name=item.name,
        vendor=item.vendor,
        model=item.model,
        serial_number=item.serial_number,
        adapter_key=item.adapter_key,
        endpoint_uri=item.endpoint_uri,
        capabilities=item.capabilities,
        pull_interval_seconds=item.pull_interval_seconds,
    )


@router.get("/{device_id}/runtime", response_model=RuntimeConfigurationView)
def get_device_runtime(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> RuntimeConfigurationView:
    item = DeviceOperationService(session).runtime_configuration(
        organization_id=organization_id,
        device_id=device_id,
    )
    return _runtime_view(item)


@router.put("/{device_id}/runtime", response_model=RuntimeConfigurationView)
def update_device_runtime(
    organization_id: UUID,
    device_id: UUID,
    payload: RuntimeConfigurationUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> RuntimeConfigurationView:
    try:
        item = DeviceOperationService(session).update_runtime_configuration(
            organization_id=organization_id,
            device_id=device_id,
            site=payload.site,
            protocol_preference=payload.protocol_preference,
            timeout_seconds=payload.timeout_seconds,
            actor_user_id=identity.principal.user.id,
        )
        return _runtime_view(item)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{device_id}/credential", response_model=CredentialRotationView)
def rotate_gateway_credential(
    organization_id: UUID,
    device_id: UUID,
    payload: GatewayCredentialUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CredentialRotationView:
    device = _device(session, organization_id, device_id)
    try:
        cipher = build_device_secret_cipher(settings)
        item = DevicePlatformService(session).rotate_credential(
            device=device,
            secret={"bearer_token": payload.bearer_token},
            cipher=cipher,
            actor_user_id=identity.principal.user.id,
        )
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CredentialRotationView(
        id=item.id,
        device_id=item.device_id,
        version=item.version,
        key_id=item.key_id,
        created_at=item.created_at,
    )


def _enqueue_operation(
    *,
    session: Session,
    organization_id: UUID,
    device_id: UUID,
    operation_type: str,
    identity: RequestIdentity,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> DeviceOperationView:
    try:
        item = DeviceOperationService(session).enqueue(
            organization_id=organization_id,
            device_id=device_id,
            operation_type=operation_type,
            requested_by=identity.principal.user.id,
            window_start=start_at,
            window_end=end_at,
        )
        session.commit()
        return _operation_view(item)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{device_id}/diagnostics",
    response_model=DeviceOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_device_diagnostics(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.pull")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceOperationView:
    return _enqueue_operation(
        session=session,
        organization_id=organization_id,
        device_id=device_id,
        operation_type="diagnostics",
        identity=identity,
    )


@router.post(
    "/{device_id}/pull-now",
    response_model=DeviceOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_immediate_pull(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.pull")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceOperationView:
    return _enqueue_operation(
        session=session,
        organization_id=organization_id,
        device_id=device_id,
        operation_type="immediate_pull",
        identity=identity,
    )


@router.post(
    "/{device_id}/historical-pull",
    response_model=DeviceOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_historical_pull(
    organization_id: UUID,
    device_id: UUID,
    payload: HistoricalPullRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.pull")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceOperationView:
    return _enqueue_operation(
        session=session,
        organization_id=organization_id,
        device_id=device_id,
        operation_type="historical_pull",
        identity=identity,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
