from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.attendance.engine import AttendanceEngineService
from hajiriflow.attendance.manual import ManualAttendanceService
from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import (
    AttendanceDayRemark,
    AttendanceImportRow,
    AttendanceImportSession,
    AttendancePeriodLock,
    AttendancePolicy,
    AttendanceRecordDetail,
    ManualAttendanceEvent,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/attendance-v2",
    tags=["attendance-v2"],
)


class AttendancePolicyUpdate(BaseModel):
    duplicate_window_seconds: int = Field(default=120, ge=0, le=3600)
    pre_shift_window_minutes: int = Field(default=240, ge=0, le=1440)
    post_shift_window_minutes: int = Field(default=480, ge=0, le=1440)
    manual_approval_required: bool = True


class AttendancePolicyView(AttendancePolicyUpdate):
    organization_id: UUID


class ManualEventCreate(BaseModel):
    employee_id: UUID
    event_time: datetime
    event_type: str = Field(pattern=r"^(in|out)$")
    reason: str = Field(min_length=1, max_length=2000)
    evidence_note: str | None = Field(default=None, max_length=4000)


class ManualEventDecision(BaseModel):
    approve: bool
    reason: str = Field(min_length=1, max_length=2000)


class ReasonPayload(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ManualEventView(BaseModel):
    id: UUID
    employee_id: UUID
    event_time: datetime
    event_type: str
    status: str
    reason: str
    evidence_note: str | None
    requested_by: UUID
    decided_by: UUID | None
    decision_reason: str | None
    requested_at: datetime
    decided_at: datetime | None
    revoked_at: datetime | None


class ImportSessionView(BaseModel):
    id: UUID
    filename: str
    content_sha256: str
    strict_mode: bool
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    applied_rows: int
    created_at: datetime
    applied_at: datetime | None


class ImportRowView(BaseModel):
    row_number: int
    raw_data: dict
    normalized_data: dict
    errors: list
    is_valid: bool
    applied_event_id: UUID | None


class RemarkCreate(BaseModel):
    employee_id: UUID
    work_date: date
    remark: str = Field(min_length=1, max_length=4000)


class RemarkView(BaseModel):
    id: UUID
    employee_id: UUID
    work_date: date
    remark: str
    created_by: UUID
    created_at: datetime


class PeriodLockCreate(BaseModel):
    starts_on: date
    ends_on: date
    reason: str = Field(min_length=1, max_length=2000)


class PeriodLockView(BaseModel):
    id: UUID
    starts_on: date
    ends_on: date
    status: str
    reason: str
    locked_by: UUID
    locked_at: datetime
    reopened_by: UUID | None
    reopened_at: datetime | None
    reopen_reason: str | None


class AttendanceEngineView(BaseModel):
    id: UUID
    employee_id: UUID
    work_date: date
    shift_id: UUID | None
    check_in_at: datetime | None
    check_out_at: datetime | None
    worked_minutes: int
    late_minutes: int
    source_event_count: int
    source_revision: int
    calculation_version: str
    base_status: str
    day_status: str
    planned_minutes: int
    break_minutes: int
    early_arrival_minutes: int
    early_departure_minutes: int
    late_departure_minutes: int
    regular_overtime_minutes: int
    holiday_overtime_minutes: int
    duplicate_event_count: int
    input_fingerprint: str
    engine_version: str
    explanation_trace: list


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _policy_view(item: AttendancePolicy) -> AttendancePolicyView:
    return AttendancePolicyView(
        organization_id=item.organization_id,
        duplicate_window_seconds=item.duplicate_window_seconds,
        pre_shift_window_minutes=item.pre_shift_window_minutes,
        post_shift_window_minutes=item.post_shift_window_minutes,
        manual_approval_required=item.manual_approval_required,
    )


def _event_view(item: ManualAttendanceEvent) -> ManualEventView:
    return ManualEventView(
        id=item.id,
        employee_id=item.employee_id,
        event_time=item.event_time,
        event_type=item.event_type,
        status=item.status,
        reason=item.reason,
        evidence_note=item.evidence_note,
        requested_by=item.requested_by,
        decided_by=item.decided_by,
        decision_reason=item.decision_reason,
        requested_at=item.requested_at,
        decided_at=item.decided_at,
        revoked_at=item.revoked_at,
    )


def _import_view(item: AttendanceImportSession) -> ImportSessionView:
    return ImportSessionView(
        id=item.id,
        filename=item.filename,
        content_sha256=item.content_sha256,
        strict_mode=item.strict_mode,
        status=item.status,
        total_rows=item.total_rows,
        valid_rows=item.valid_rows,
        invalid_rows=item.invalid_rows,
        applied_rows=item.applied_rows,
        created_at=item.created_at,
        applied_at=item.applied_at,
    )


def _lock_view(item: AttendancePeriodLock) -> PeriodLockView:
    return PeriodLockView(
        id=item.id,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        status=item.status,
        reason=item.reason,
        locked_by=item.locked_by,
        locked_at=item.locked_at,
        reopened_by=item.reopened_by,
        reopened_at=item.reopened_at,
        reopen_reason=item.reopen_reason,
    )


def _engine_view(
    session: Session,
    record: AttendanceRecord,
) -> AttendanceEngineView:
    detail = session.get(AttendanceRecordDetail, record.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="attendance record has not been calculated by the v2 engine",
        )
    return AttendanceEngineView(
        id=record.id,
        employee_id=record.employee_id,
        work_date=record.work_date,
        shift_id=record.shift_id,
        check_in_at=record.check_in_at,
        check_out_at=record.check_out_at,
        worked_minutes=record.worked_minutes,
        late_minutes=record.late_minutes,
        source_event_count=record.source_punch_count,
        source_revision=record.source_revision,
        calculation_version=record.calculation_version,
        base_status=record.status,
        day_status=detail.day_status,
        planned_minutes=detail.planned_minutes,
        break_minutes=detail.break_minutes,
        early_arrival_minutes=detail.early_arrival_minutes,
        early_departure_minutes=detail.early_departure_minutes,
        late_departure_minutes=detail.late_departure_minutes,
        regular_overtime_minutes=detail.regular_overtime_minutes,
        holiday_overtime_minutes=detail.holiday_overtime_minutes,
        duplicate_event_count=detail.duplicate_event_count,
        input_fingerprint=detail.input_fingerprint,
        engine_version=detail.engine_version,
        explanation_trace=detail.explanation_trace,
    )


@router.get("/policy", response_model=AttendancePolicyView)
def get_attendance_policy(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendancePolicyView:
    return _policy_view(ManualAttendanceService(session).policy(organization_id))


@router.put("/policy", response_model=AttendancePolicyView)
def update_attendance_policy(
    organization_id: UUID,
    payload: AttendancePolicyUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendancePolicyView:
    try:
        item = ManualAttendanceService(session).update_policy(
            organization_id=organization_id,
            duplicate_window_seconds=payload.duplicate_window_seconds,
            pre_shift_window_minutes=payload.pre_shift_window_minutes,
            post_shift_window_minutes=payload.post_shift_window_minutes,
            manual_approval_required=payload.manual_approval_required,
            actor_user_id=identity.principal.user.id,
        )
        return _policy_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post(
    "/manual-events",
    response_model=ManualEventView,
    status_code=status.HTTP_201_CREATED,
)
def request_manual_event(
    organization_id: UUID,
    payload: ManualEventCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ManualEventView:
    try:
        item = ManualAttendanceService(session).request_event(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            event_time=payload.event_time,
            event_type=payload.event_type,
            reason=payload.reason,
            evidence_note=payload.evidence_note,
            requested_by=identity.principal.user.id,
        )
        return _event_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/manual-events", response_model=list[ManualEventView])
def list_manual_events(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
    event_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ManualEventView]:
    query = select(ManualAttendanceEvent).where(
        ManualAttendanceEvent.organization_id == organization_id
    )
    if employee_id is not None:
        query = query.where(ManualAttendanceEvent.employee_id == employee_id)
    if event_status is not None:
        query = query.where(ManualAttendanceEvent.status == event_status)
    items = session.scalars(
        query.order_by(
            ManualAttendanceEvent.event_time.desc(),
            ManualAttendanceEvent.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return [_event_view(item) for item in items]


@router.post("/manual-events/{event_id}/decision", response_model=ManualEventView)
def decide_manual_event(
    organization_id: UUID,
    event_id: UUID,
    payload: ManualEventDecision,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ManualEventView:
    try:
        item = ManualAttendanceService(session).decide_event(
            organization_id=organization_id,
            event_id=event_id,
            approve=payload.approve,
            decision_reason=payload.reason,
            decided_by=identity.principal.user.id,
        )
        return _event_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/manual-events/{event_id}/revoke", response_model=ManualEventView)
def revoke_manual_event(
    organization_id: UUID,
    event_id: UUID,
    payload: ReasonPayload,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ManualEventView:
    try:
        item = ManualAttendanceService(session).revoke_event(
            organization_id=organization_id,
            event_id=event_id,
            reason=payload.reason,
            actor_user_id=identity.principal.user.id,
        )
        return _event_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/manual-imports/template")
def download_manual_import_template(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
) -> Response:
    del organization_id
    return Response(
        content=ManualAttendanceService.template_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="hajiriflow-manual-attendance.xlsx"'
        },
    )


@router.post(
    "/manual-imports/preview",
    response_model=ImportSessionView,
    status_code=status.HTTP_201_CREATED,
)
async def preview_manual_import(
    organization_id: UUID,
    request: Request,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
    filename: Annotated[str, Query(min_length=1, max_length=240)] = "attendance-import.xlsx",
    strict: Annotated[bool, Query()] = True,
) -> ImportSessionView:
    try:
        item = ManualAttendanceService(session).preview_import(
            organization_id=organization_id,
            filename=filename,
            content=await request.body(),
            strict_mode=strict,
            requested_by=identity.principal.user.id,
        )
        return _import_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/manual-imports/{import_session_id}", response_model=ImportSessionView)
def get_manual_import(
    organization_id: UUID,
    import_session_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ImportSessionView:
    item = session.get(AttendanceImportSession, import_session_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="attendance import session not found")
    return _import_view(item)


@router.get(
    "/manual-imports/{import_session_id}/rows",
    response_model=list[ImportRowView],
)
def get_manual_import_rows(
    organization_id: UUID,
    import_session_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[ImportRowView]:
    parent = session.get(AttendanceImportSession, import_session_id)
    if not parent or parent.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="attendance import session not found")
    rows = session.scalars(
        select(AttendanceImportRow)
        .where(AttendanceImportRow.session_id == import_session_id)
        .order_by(AttendanceImportRow.row_number)
    ).all()
    return [
        ImportRowView(
            row_number=item.row_number,
            raw_data=item.raw_data,
            normalized_data=item.normalized_data,
            errors=item.errors,
            is_valid=item.is_valid,
            applied_event_id=item.applied_event_id,
        )
        for item in rows
    ]


@router.post(
    "/manual-imports/{import_session_id}/apply",
    response_model=ImportSessionView,
)
def apply_manual_import(
    organization_id: UUID,
    import_session_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ImportSessionView:
    try:
        item = ManualAttendanceService(session).apply_import(
            organization_id=organization_id,
            import_session_id=import_session_id,
            approved_by=identity.principal.user.id,
        )
        return _import_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post(
    "/remarks",
    response_model=RemarkView,
    status_code=status.HTTP_201_CREATED,
)
def add_attendance_remark(
    organization_id: UUID,
    payload: RemarkCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> RemarkView:
    try:
        item = ManualAttendanceService(session).add_remark(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            work_date=payload.work_date,
            remark=payload.remark,
            created_by=identity.principal.user.id,
        )
        return RemarkView(
            id=item.id,
            employee_id=item.employee_id,
            work_date=item.work_date,
            remark=item.remark,
            created_by=item.created_by,
            created_at=item.created_at,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/remarks", response_model=list[RemarkView])
def list_attendance_remarks(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID, Query()],
    work_date: Annotated[date, Query()],
) -> list[RemarkView]:
    items = session.scalars(
        select(AttendanceDayRemark)
        .where(
            AttendanceDayRemark.organization_id == organization_id,
            AttendanceDayRemark.employee_id == employee_id,
            AttendanceDayRemark.work_date == work_date,
        )
        .order_by(AttendanceDayRemark.created_at, AttendanceDayRemark.id)
    ).all()
    return [
        RemarkView(
            id=item.id,
            employee_id=item.employee_id,
            work_date=item.work_date,
            remark=item.remark,
            created_by=item.created_by,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post(
    "/period-locks",
    response_model=PeriodLockView,
    status_code=status.HTTP_201_CREATED,
)
def lock_attendance_period(
    organization_id: UUID,
    payload: PeriodLockCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PeriodLockView:
    try:
        item = ManualAttendanceService(session).lock_period(
            organization_id=organization_id,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            reason=payload.reason,
            locked_by=identity.principal.user.id,
        )
        return _lock_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/period-locks/{lock_id}/reopen", response_model=PeriodLockView)
def reopen_attendance_period(
    organization_id: UUID,
    lock_id: UUID,
    payload: ReasonPayload,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PeriodLockView:
    try:
        item = ManualAttendanceService(session).reopen_period(
            organization_id=organization_id,
            lock_id=lock_id,
            reason=payload.reason,
            reopened_by=identity.principal.user.id,
        )
        return _lock_view(item)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/period-locks", response_model=list[PeriodLockView])
def list_attendance_period_locks(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PeriodLockView]:
    items = session.scalars(
        select(AttendancePeriodLock)
        .where(AttendancePeriodLock.organization_id == organization_id)
        .order_by(AttendancePeriodLock.starts_on.desc(), AttendancePeriodLock.id.desc())
    ).all()
    return [_lock_view(item) for item in items]


@router.post(
    "/engine/{employee_id}/{work_date}/calculate",
    response_model=AttendanceEngineView,
)
def calculate_attendance_v2(
    organization_id: UUID,
    employee_id: UUID,
    work_date: date,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendanceEngineView:
    try:
        record = AttendanceEngineService(session).calculate_day(
            organization_id=organization_id,
            employee_id=employee_id,
            work_date=work_date,
            actor_user_id=identity.principal.user.id,
        )
        return _engine_view(session, record)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get(
    "/engine/{employee_id}/{work_date}",
    response_model=AttendanceEngineView,
)
def get_attendance_v2(
    organization_id: UUID,
    employee_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendanceEngineView:
    record = session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == organization_id,
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_date == work_date,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="attendance record not found")
    return _engine_view(session, record)
