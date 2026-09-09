from datetime import date, datetime
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
from hajiriflow.attendance.engine import ENGINE_VERSION, AttendanceEngineService
from hajiriflow.attendance.service import AttendanceService
from hajiriflow.db.models.attendance import (
    AttendanceCorrection,
    AttendanceHistory,
    AttendanceRecord,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/attendance",
    tags=["attendance"],
)


class AttendanceCalculate(BaseModel):
    employee_id: UUID
    work_date: date
    calculation_version: Literal["attendance-v2"] = ENGINE_VERSION


class AttendanceRecordView(BaseModel):
    id: UUID
    organization_id: UUID
    employee_id: UUID
    work_date: date
    shift_id: UUID | None
    check_in_at: datetime | None
    check_out_at: datetime | None
    worked_minutes: int
    late_minutes: int
    status: str
    calculation_version: str
    source_punch_count: int
    source_revision: int
    calculated_at: datetime
    updated_at: datetime


class AttendanceCorrectionCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    proposed_check_in_at: datetime | None = None
    proposed_check_out_at: datetime | None = None
    proposed_status: Literal["present", "absent", "partial"] | None = None


class AttendanceCorrectionDecision(BaseModel):
    approve: bool
    reason: str = Field(min_length=5, max_length=2000)


class AttendanceCorrectionView(BaseModel):
    id: UUID
    organization_id: UUID
    attendance_record_id: UUID
    requested_by: UUID
    reason: str
    proposed_check_in_at: datetime | None
    proposed_check_out_at: datetime | None
    proposed_status: str | None
    status: str
    decided_by: UUID | None
    decision_reason: str | None
    requested_at: datetime
    decided_at: datetime | None


class AttendanceHistoryView(BaseModel):
    id: UUID
    attendance_record_id: UUID
    correction_id: UUID | None
    actor_user_id: UUID | None
    event_type: str
    reason: str | None
    snapshot: dict
    occurred_at: datetime


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _record_view(item: AttendanceRecord) -> AttendanceRecordView:
    return AttendanceRecordView(
        id=item.id,
        organization_id=item.organization_id,
        employee_id=item.employee_id,
        work_date=item.work_date,
        shift_id=item.shift_id,
        check_in_at=item.check_in_at,
        check_out_at=item.check_out_at,
        worked_minutes=item.worked_minutes,
        late_minutes=item.late_minutes,
        status=item.status,
        calculation_version=item.calculation_version,
        source_punch_count=item.source_punch_count,
        source_revision=item.source_revision,
        calculated_at=item.calculated_at,
        updated_at=item.updated_at,
    )


def _correction_view(item: AttendanceCorrection) -> AttendanceCorrectionView:
    return AttendanceCorrectionView(
        id=item.id,
        organization_id=item.organization_id,
        attendance_record_id=item.attendance_record_id,
        requested_by=item.requested_by,
        reason=item.reason,
        proposed_check_in_at=item.proposed_check_in_at,
        proposed_check_out_at=item.proposed_check_out_at,
        proposed_status=item.proposed_status,
        status=item.status,
        decided_by=item.decided_by,
        decision_reason=item.decision_reason,
        requested_at=item.requested_at,
        decided_at=item.decided_at,
    )


@router.get("/records", response_model=list[AttendanceRecordView])
def list_attendance_records(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    attendance_status: Literal["present", "absent", "partial"] | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AttendanceRecordView]:
    query = select(AttendanceRecord).where(
        AttendanceRecord.organization_id == organization_id
    )
    if employee_id is not None:
        query = query.where(AttendanceRecord.employee_id == employee_id)
    if from_date is not None:
        query = query.where(AttendanceRecord.work_date >= from_date)
    if to_date is not None:
        query = query.where(AttendanceRecord.work_date <= to_date)
    if attendance_status is not None:
        query = query.where(AttendanceRecord.status == attendance_status)
    items = session.scalars(
        query.order_by(AttendanceRecord.work_date.desc(), AttendanceRecord.employee_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [_record_view(item) for item in items]


@router.post("/calculate", response_model=AttendanceRecordView)
def calculate_attendance(
    organization_id: UUID,
    payload: AttendanceCalculate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendanceRecordView:
    try:
        item = AttendanceEngineService(session).calculate_day(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            work_date=payload.work_date,
            actor_user_id=identity.principal.user.id,
        )
        session.commit()
        return _record_view(item)
    except (LookupError, ValueError) as exc:
        raise _service_error(exc) from exc


@router.post(
    "/records/{attendance_record_id}/corrections",
    response_model=AttendanceCorrectionView,
    status_code=status.HTTP_201_CREATED,
)
def request_attendance_correction(
    organization_id: UUID,
    attendance_record_id: UUID,
    payload: AttendanceCorrectionCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendanceCorrectionView:
    try:
        item = AttendanceService(session).request_correction(
            organization_id=organization_id,
            attendance_record_id=attendance_record_id,
            requested_by=identity.principal.user.id,
            reason=payload.reason,
            proposed_check_in_at=payload.proposed_check_in_at,
            proposed_check_out_at=payload.proposed_check_out_at,
            proposed_status=payload.proposed_status,
        )
        session.commit()
        return _correction_view(item)
    except (LookupError, ValueError) as exc:
        raise _service_error(exc) from exc


@router.post(
    "/corrections/{correction_id}/decision",
    response_model=AttendanceCorrectionView,
)
def decide_attendance_correction(
    organization_id: UUID,
    correction_id: UUID,
    payload: AttendanceCorrectionDecision,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AttendanceCorrectionView:
    try:
        item = AttendanceService(session).decide_correction(
            organization_id=organization_id,
            correction_id=correction_id,
            decided_by=identity.principal.user.id,
            approve=payload.approve,
            decision_reason=payload.reason,
        )
        session.commit()
        return _correction_view(item)
    except (LookupError, ValueError) as exc:
        raise _service_error(exc) from exc


@router.get("/corrections", response_model=list[AttendanceCorrectionView])
def list_attendance_corrections(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    correction_status: Literal["pending", "approved", "rejected"] | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AttendanceCorrectionView]:
    query = select(AttendanceCorrection).where(
        AttendanceCorrection.organization_id == organization_id
    )
    if correction_status is not None:
        query = query.where(AttendanceCorrection.status == correction_status)
    items = session.scalars(
        query.order_by(AttendanceCorrection.requested_at.desc()).limit(limit)
    ).all()
    return [_correction_view(item) for item in items]


@router.get(
    "/records/{attendance_record_id}/history",
    response_model=list[AttendanceHistoryView],
)
def attendance_history(
    organization_id: UUID,
    attendance_record_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[AttendanceHistoryView]:
    record = session.get(AttendanceRecord, attendance_record_id)
    if not record or record.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="attendance record not found",
        )
    items = session.scalars(
        select(AttendanceHistory)
        .where(
            AttendanceHistory.organization_id == organization_id,
            AttendanceHistory.attendance_record_id == attendance_record_id,
        )
        .order_by(AttendanceHistory.occurred_at, AttendanceHistory.id)
    ).all()
    return [
        AttendanceHistoryView(
            id=item.id,
            attendance_record_id=item.attendance_record_id,
            correction_id=item.correction_id,
            actor_user_id=item.actor_user_id,
            event_type=item.event_type,
            reason=item.reason,
            snapshot=item.snapshot,
            occurred_at=item.occurred_at,
        )
        for item in items
    ]
