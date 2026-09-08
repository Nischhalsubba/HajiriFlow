from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
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
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.device_baseline import (
    DeviceDiagnosticSnapshot,
    DeviceIdentityArchive,
    DeviceJob,
)
from hajiriflow.db.models.workforce import Employee
from hajiriflow.db.models.workforce_profile import EmployeeProfile
from hajiriflow.device_platform.jobs import DeviceJobService
from hajiriflow.device_platform.runtime import device_secret_cipher_from_environment
from hajiriflow.device_platform.service import DevicePlatformService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/device-platform",
    tags=["device-platform"],
)


class CredentialRotateRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4000)


class CredentialRotateView(BaseModel):
    credential_id: UUID
    version: int
    key_id: str


class DeviceJobView(BaseModel):
    id: UUID
    device_id: UUID
    job_type: str
    status: str
    result: dict
    error_code: str | None
    error_detail: str | None
    requested_by: UUID | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class HistoricalPullRequest(BaseModel):
    start_at: datetime
    end_at: datetime


class PushUserRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)


class EmployeeEnrollmentPreview(BaseModel):
    employee_id: UUID
    employee_code: str
    display_name: str
    external_user_id: str
    already_registered: bool


class BulkEnrollmentRequest(BaseModel):
    employee_ids: list[UUID] = Field(min_length=1, max_length=500)


class DeviceComparisonView(BaseModel):
    unknown_device_user_ids: list[UUID]
    missing_employee_ids: list[UUID]
    inactive_device_user_ids: list[UUID]


class MigrationPreviewRequest(BaseModel):
    target_device_id: UUID
    external_user_ids: list[str] = Field(min_length=1, max_length=500)


class MigrationPreviewItem(BaseModel):
    external_user_id: str
    source_exists: bool
    target_conflict: bool
    can_migrate: bool


class ArchiveRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=200)


class RestoreArchiveRequest(BaseModel):
    archive_id: UUID


class ArchiveView(BaseModel):
    id: UUID
    device_id: UUID
    external_user_id: str
    content_sha256: str
    created_by: UUID | None
    created_at: datetime


class DiagnosticView(BaseModel):
    id: UUID
    device_id: UUID
    reachable: bool
    firmware_version: str | None
    device_time: datetime | None
    message: str | None
    metadata: dict
    observed_at: datetime


class DeviceUserPageItem(BaseModel):
    id: UUID
    external_user_id: str
    display_name: str | None
    privilege: str | None
    active: bool
    template_count: int
    mapped_employee_id: UUID | None
    last_seen_at: datetime


class DeviceUserPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DeviceUserPageItem]


class UnlinkedPunchView(BaseModel):
    id: UUID
    device_id: UUID
    device_user_identifier: str
    occurred_at: datetime
    punch_kind: str
    verification_method: str | None
    received_at: datetime


def _device(session: Session, organization_id: UUID, device_id: UUID) -> Device:
    item = session.get(Device, device_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="device not found")
    return item


def _job_view(item: DeviceJob) -> DeviceJobView:
    return DeviceJobView(
        id=item.id,
        device_id=item.device_id,
        job_type=item.job_type,
        status=item.status,
        result=item.result,
        error_code=item.error_code,
        error_detail=item.error_detail,
        requested_by=item.requested_by,
        created_at=item.created_at,
        started_at=item.started_at,
        ended_at=item.ended_at,
    )


def _queue(
    session: Session,
    *,
    device: Device,
    job_type: str,
    payload: dict,
    actor_user_id: UUID,
) -> DeviceJobView:
    try:
        job = DeviceJobService(session).enqueue(
            device=device,
            job_type=job_type,
            payload=payload,
            requested_by=actor_user_id,
        )
        session.commit()
        return _job_view(job)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/supported-adapters")
def supported_adapters(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
) -> dict:
    del organization_id
    return {
        "adapters": [
            {
                "key": "hajiriflow_gateway_v1",
                "transport": "https",
                "network_owner": "worker",
                "contract": "HajiriFlow Device Gateway v1",
            }
        ]
    }


@router.post(
    "/devices/{device_id}/credentials/rotate",
    response_model=CredentialRotateView,
)
def rotate_credential(
    organization_id: UUID,
    device_id: UUID,
    payload: CredentialRotateRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CredentialRotateView:
    device = _device(session, organization_id, device_id)
    try:
        cipher = device_secret_cipher_from_environment()
        credential = DevicePlatformService(session).rotate_credential(
            device=device,
            secret={"token": payload.token},
            cipher=cipher,
            actor_user_id=identity.principal.user.id,
        )
        session.commit()
        return CredentialRotateView(
            credential_id=credential.id,
            version=credential.version,
            key_id=credential.key_id,
        )
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/devices/{device_id}/diagnostics", response_model=DeviceJobView)
def queue_diagnostics(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="diagnostics",
        payload={},
        actor_user_id=identity.principal.user.id,
    )


@router.post("/devices/{device_id}/pull", response_model=DeviceJobView)
def queue_immediate_pull(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.pull")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="immediate_pull",
        payload={},
        actor_user_id=identity.principal.user.id,
    )


@router.post("/devices/{device_id}/pull/historical", response_model=DeviceJobView)
def queue_historical_pull(
    organization_id: UUID,
    device_id: UUID,
    payload: HistoricalPullRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.pull")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    if payload.start_at.tzinfo is None or payload.end_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="historical pull timestamps need a timezone")
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="historical_pull",
        payload={
            "start_at": payload.start_at.astimezone(UTC).isoformat(),
            "end_at": payload.end_at.astimezone(UTC).isoformat(),
        },
        actor_user_id=identity.principal.user.id,
    )


@router.post("/devices/{device_id}/users/sync", response_model=DeviceJobView)
def queue_user_sync(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="sync_users",
        payload={},
        actor_user_id=identity.principal.user.id,
    )


@router.post("/devices/{device_id}/users/push", response_model=DeviceJobView)
def queue_user_push(
    organization_id: UUID,
    device_id: UUID,
    payload: PushUserRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="push_user",
        payload={
            "external_user_id": payload.external_user_id.strip(),
            "display_name": payload.display_name.strip() if payload.display_name else None,
        },
        actor_user_id=identity.principal.user.id,
    )


def _employee_external_id(employee: Employee, profile: EmployeeProfile | None) -> str:
    return str(profile.attendance_id) if profile and profile.attendance_id else employee.employee_code


def _enrollment_rows(
    session: Session,
    *,
    organization_id: UUID,
    device_id: UUID,
    employee_ids: list[UUID] | None = None,
) -> list[EmployeeEnrollmentPreview]:
    query = (
        select(Employee, EmployeeProfile)
        .outerjoin(EmployeeProfile, EmployeeProfile.employee_id == Employee.id)
        .where(
            Employee.organization_id == organization_id,
            Employee.status == "active",
        )
        .order_by(Employee.employee_code)
    )
    if employee_ids:
        query = query.where(Employee.id.in_(employee_ids))
    existing = set(
        session.scalars(
            select(DeviceUser.external_user_id).where(DeviceUser.device_id == device_id)
        ).all()
    )
    return [
        EmployeeEnrollmentPreview(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            display_name=employee.display_name,
            external_user_id=_employee_external_id(employee, profile),
            already_registered=_employee_external_id(employee, profile) in existing,
        )
        for employee, profile in session.execute(query).all()
    ]


@router.get(
    "/devices/{device_id}/enrollment/preview",
    response_model=list[EmployeeEnrollmentPreview],
)
def preview_bulk_enrollment(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[EmployeeEnrollmentPreview]:
    _device(session, organization_id, device_id)
    return _enrollment_rows(
        session,
        organization_id=organization_id,
        device_id=device_id,
    )


@router.post(
    "/devices/{device_id}/enrollment/apply",
    response_model=list[DeviceJobView],
)
def apply_bulk_enrollment(
    organization_id: UUID,
    device_id: UUID,
    payload: BulkEnrollmentRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeviceJobView]:
    device = _device(session, organization_id, device_id)
    rows = _enrollment_rows(
        session,
        organization_id=organization_id,
        device_id=device_id,
        employee_ids=payload.employee_ids,
    )
    found = {item.employee_id for item in rows}
    if found != set(payload.employee_ids):
        raise HTTPException(status_code=400, detail="one or more employees are invalid or inactive")
    service = DeviceJobService(session)
    jobs = []
    for item in rows:
        if item.already_registered:
            continue
        jobs.append(
            service.enqueue(
                device=device,
                job_type="push_user",
                payload={
                    "external_user_id": item.external_user_id,
                    "display_name": item.display_name,
                },
                requested_by=identity.principal.user.id,
            )
        )
    session.commit()
    return [_job_view(item) for item in jobs]


@router.get("/devices/{device_id}/comparison", response_model=DeviceComparisonView)
def comparison_preview(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceComparisonView:
    _device(session, organization_id, device_id)
    users = session.scalars(
        select(DeviceUser).where(DeviceUser.device_id == device_id)
    ).all()
    mapped_ids = set(
        session.scalars(
            select(DeviceEmployeeMapping.device_user_id).where(
                DeviceEmployeeMapping.organization_id == organization_id,
                DeviceEmployeeMapping.status == "active",
            )
        ).all()
    )
    mapped_employee_ids = set(
        session.scalars(
            select(DeviceEmployeeMapping.employee_id)
            .join(DeviceUser, DeviceUser.id == DeviceEmployeeMapping.device_user_id)
            .where(
                DeviceUser.device_id == device_id,
                DeviceEmployeeMapping.status == "active",
            )
        ).all()
    )
    active_employee_ids = set(
        session.scalars(
            select(Employee.id).where(
                Employee.organization_id == organization_id,
                Employee.status == "active",
            )
        ).all()
    )
    return DeviceComparisonView(
        unknown_device_user_ids=[item.id for item in users if item.id not in mapped_ids],
        missing_employee_ids=sorted(active_employee_ids - mapped_employee_ids, key=str),
        inactive_device_user_ids=[item.id for item in users if not item.active],
    )


@router.post(
    "/devices/{device_id}/migration/preview",
    response_model=list[MigrationPreviewItem],
)
def migration_preview(
    organization_id: UUID,
    device_id: UUID,
    payload: MigrationPreviewRequest,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[MigrationPreviewItem]:
    source = _device(session, organization_id, device_id)
    target = _device(session, organization_id, payload.target_device_id)
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="source and target devices must differ")
    source_ids = set(
        session.scalars(
            select(DeviceUser.external_user_id).where(DeviceUser.device_id == source.id)
        ).all()
    )
    target_ids = set(
        session.scalars(
            select(DeviceUser.external_user_id).where(DeviceUser.device_id == target.id)
        ).all()
    )
    return [
        MigrationPreviewItem(
            external_user_id=value,
            source_exists=value in source_ids,
            target_conflict=value in target_ids,
            can_migrate=value in source_ids and value not in target_ids,
        )
        for value in payload.external_user_ids
    ]


@router.post(
    "/devices/{device_id}/migration/apply",
    response_model=list[DeviceJobView],
)
def migration_apply(
    organization_id: UUID,
    device_id: UUID,
    payload: MigrationPreviewRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeviceJobView]:
    source = _device(session, organization_id, device_id)
    _device(session, organization_id, payload.target_device_id)
    source_ids = set(
        session.scalars(
            select(DeviceUser.external_user_id).where(DeviceUser.device_id == source.id)
        ).all()
    )
    target_ids = set(
        session.scalars(
            select(DeviceUser.external_user_id).where(
                DeviceUser.device_id == payload.target_device_id
            )
        ).all()
    )
    conflicts = [value for value in payload.external_user_ids if value in target_ids]
    missing = [value for value in payload.external_user_ids if value not in source_ids]
    if conflicts or missing:
        raise HTTPException(
            status_code=409,
            detail={"target_conflicts": conflicts, "missing_source_users": missing},
        )
    service = DeviceJobService(session)
    jobs = [
        service.enqueue(
            device=source,
            job_type="migrate_user",
            payload={
                "target_device_id": str(payload.target_device_id),
                "external_user_id": value,
            },
            requested_by=identity.principal.user.id,
        )
        for value in payload.external_user_ids
    ]
    session.commit()
    return [_job_view(item) for item in jobs]


@router.post("/devices/{device_id}/archives", response_model=DeviceJobView)
def queue_archive(
    organization_id: UUID,
    device_id: UUID,
    payload: ArchiveRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="archive_user",
        payload={"external_user_id": payload.external_user_id.strip()},
        actor_user_id=identity.principal.user.id,
    )


@router.post("/devices/{device_id}/archives/restore", response_model=DeviceJobView)
def queue_restore(
    organization_id: UUID,
    device_id: UUID,
    payload: RestoreArchiveRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    archive = session.get(DeviceIdentityArchive, payload.archive_id)
    if not archive or archive.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="device archive not found")
    return _queue(
        session,
        device=_device(session, organization_id, device_id),
        job_type="restore_user",
        payload={"archive_id": str(payload.archive_id)},
        actor_user_id=identity.principal.user.id,
    )


@router.get("/archives", response_model=list[ArchiveView])
def list_archives(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[ArchiveView]:
    items = session.scalars(
        select(DeviceIdentityArchive)
        .where(DeviceIdentityArchive.organization_id == organization_id)
        .order_by(DeviceIdentityArchive.created_at.desc())
        .limit(500)
    ).all()
    return [
        ArchiveView(
            id=item.id,
            device_id=item.device_id,
            external_user_id=item.external_user_id,
            content_sha256=item.content_sha256,
            created_by=item.created_by,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.get("/jobs", response_model=list[DeviceJobView])
def list_jobs(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    device_id: Annotated[UUID | None, Query()] = None,
    job_status: Annotated[
        Literal["queued", "running", "succeeded", "failed", "cancelled"] | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[DeviceJobView]:
    query = select(DeviceJob).where(DeviceJob.organization_id == organization_id)
    if device_id:
        query = query.where(DeviceJob.device_id == device_id)
    if job_status:
        query = query.where(DeviceJob.status == job_status)
    items = session.scalars(query.order_by(DeviceJob.created_at.desc()).limit(limit)).all()
    return [_job_view(item) for item in items]


@router.get("/jobs/{job_id}", response_model=DeviceJobView)
def get_job(
    organization_id: UUID,
    job_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceJobView:
    item = session.get(DeviceJob, job_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="device job not found")
    return _job_view(item)


@router.get("/devices/{device_id}/diagnostics", response_model=list[DiagnosticView])
def diagnostic_history(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DiagnosticView]:
    _device(session, organization_id, device_id)
    items = session.scalars(
        select(DeviceDiagnosticSnapshot)
        .where(DeviceDiagnosticSnapshot.device_id == device_id)
        .order_by(DeviceDiagnosticSnapshot.observed_at.desc())
        .limit(100)
    ).all()
    return [
        DiagnosticView(
            id=item.id,
            device_id=item.device_id,
            reachable=item.reachable,
            firmware_version=item.firmware_version,
            device_time=item.device_time,
            message=item.message,
            metadata=item.metadata,
            observed_at=item.observed_at,
        )
        for item in items
    ]


@router.get("/devices/{device_id}/users", response_model=DeviceUserPage)
def paginated_device_users(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DeviceUserPage:
    _device(session, organization_id, device_id)
    filters = [DeviceUser.device_id == device_id]
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            DeviceUser.external_user_id.ilike(pattern)
            | DeviceUser.display_name.ilike(pattern)
        )
    total = session.scalar(select(func.count(DeviceUser.id)).where(*filters)) or 0
    rows = session.execute(
        select(DeviceUser, DeviceEmployeeMapping.employee_id)
        .outerjoin(
            DeviceEmployeeMapping,
            and_(
                DeviceEmployeeMapping.device_user_id == DeviceUser.id,
                DeviceEmployeeMapping.status == "active",
            ),
        )
        .where(*filters)
        .order_by(DeviceUser.external_user_id)
        .offset(offset)
        .limit(limit)
    ).all()
    return DeviceUserPage(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[
            DeviceUserPageItem(
                id=user.id,
                external_user_id=user.external_user_id,
                display_name=user.display_name,
                privilege=user.privilege,
                active=user.active,
                template_count=user.template_count,
                mapped_employee_id=employee_id,
                last_seen_at=user.last_seen_at,
            )
            for user, employee_id in rows
        ],
    )


@router.get("/unlinked-punches", response_model=list[UnlinkedPunchView])
def unlinked_punches(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 250,
) -> list[UnlinkedPunchView]:
    rows = session.execute(
        select(RawPunch)
        .outerjoin(
            DeviceUser,
            and_(
                DeviceUser.device_id == RawPunch.device_id,
                DeviceUser.external_user_id == RawPunch.device_user_identifier,
            ),
        )
        .outerjoin(
            DeviceEmployeeMapping,
            and_(
                DeviceEmployeeMapping.device_user_id == DeviceUser.id,
                DeviceEmployeeMapping.status == "active",
            ),
        )
        .where(
            RawPunch.organization_id == organization_id,
            DeviceEmployeeMapping.id.is_(None),
        )
        .order_by(RawPunch.occurred_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        UnlinkedPunchView(
            id=item.id,
            device_id=item.device_id,
            device_user_identifier=item.device_user_identifier,
            occurred_at=item.occurred_at,
            punch_kind=item.punch_kind,
            verification_method=item.verification_method,
            received_at=item.received_at,
        )
        for item in rows
    ]
