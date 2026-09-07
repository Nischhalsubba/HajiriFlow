from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
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
from hajiriflow.db.models.payroll import (
    PayrollHistory,
    PayrollLine,
    PayrollPeriod,
    PayrollRun,
)
from hajiriflow.payroll.service import PayrollService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/payroll",
    tags=["payroll"],
)


class PayrollPeriodCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    starts_on: date
    ends_on: date
    attendance_calculation_version: str = Field(min_length=1, max_length=80)


class PayrollPeriodView(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    label: str
    starts_on: date
    ends_on: date
    status: str
    attendance_calculation_version: str
    created_by: UUID
    created_at: datetime
    locked_by: UUID | None
    locked_at: datetime | None
    closed_by: UUID | None
    closed_at: datetime | None


class PayrollRunCreate(BaseModel):
    period_id: UUID
    calculation_version: str = Field(min_length=1, max_length=80)
    policy_snapshot: dict


class PayrollRunView(BaseModel):
    id: UUID
    organization_id: UUID
    period_id: UUID
    sequence: int
    status: str
    calculation_version: str
    policy_snapshot: dict
    created_by: UUID
    created_at: datetime
    submitted_at: datetime | None
    approved_by: UUID | None
    approved_at: datetime | None
    posted_by: UUID | None
    posted_at: datetime | None
    reversal_requested_by: UUID | None
    reversal_requested_at: datetime | None
    reversed_by: UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    reversal_of_run_id: UUID | None
    reversal_run_id: UUID | None


class PayrollLineCreate(BaseModel):
    employee_id: UUID
    gross_amount: Decimal = Field(ge=0)
    deduction_amount: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)
    employee_snapshot: dict
    attendance_snapshot: dict
    earnings_snapshot: dict
    deductions_snapshot: dict
    explanation: dict


class PayrollLineView(BaseModel):
    id: UUID
    run_id: UUID
    employee_id: UUID
    direction: str
    currency: str
    gross_amount: Decimal
    deduction_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    employee_snapshot: dict
    attendance_snapshot: dict
    earnings_snapshot: dict
    deductions_snapshot: dict
    explanation: dict


class ReversalRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class PayrollHistoryView(BaseModel):
    id: UUID
    run_id: UUID
    actor_user_id: UUID
    action: str
    reason: str | None
    snapshot: dict
    occurred_at: datetime


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _period_view(item: PayrollPeriod) -> PayrollPeriodView:
    return PayrollPeriodView(
        id=item.id,
        organization_id=item.organization_id,
        code=item.code,
        label=item.label,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        status=item.status,
        attendance_calculation_version=item.attendance_calculation_version,
        created_by=item.created_by,
        created_at=item.created_at,
        locked_by=item.locked_by,
        locked_at=item.locked_at,
        closed_by=item.closed_by,
        closed_at=item.closed_at,
    )


def _run_view(item: PayrollRun) -> PayrollRunView:
    return PayrollRunView(
        id=item.id,
        organization_id=item.organization_id,
        period_id=item.period_id,
        sequence=item.sequence,
        status=item.status,
        calculation_version=item.calculation_version,
        policy_snapshot=item.policy_snapshot,
        created_by=item.created_by,
        created_at=item.created_at,
        submitted_at=item.submitted_at,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        posted_by=item.posted_by,
        posted_at=item.posted_at,
        reversal_requested_by=item.reversal_requested_by,
        reversal_requested_at=item.reversal_requested_at,
        reversed_by=item.reversed_by,
        reversed_at=item.reversed_at,
        reversal_reason=item.reversal_reason,
        reversal_of_run_id=item.reversal_of_run_id,
        reversal_run_id=item.reversal_run_id,
    )


def _line_view(item: PayrollLine) -> PayrollLineView:
    return PayrollLineView(
        id=item.id,
        run_id=item.run_id,
        employee_id=item.employee_id,
        direction=item.direction,
        currency=item.currency,
        gross_amount=item.gross_amount,
        deduction_amount=item.deduction_amount,
        tax_amount=item.tax_amount,
        net_amount=item.net_amount,
        employee_snapshot=item.employee_snapshot,
        attendance_snapshot=item.attendance_snapshot,
        earnings_snapshot=item.earnings_snapshot,
        deductions_snapshot=item.deductions_snapshot,
        explanation=item.explanation,
    )


def _commit(session: Session) -> None:
    session.commit()


@router.get("/periods", response_model=list[PayrollPeriodView])
def list_periods(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PayrollPeriodView]:
    items = session.scalars(
        select(PayrollPeriod)
        .where(PayrollPeriod.organization_id == organization_id)
        .order_by(PayrollPeriod.starts_on.desc())
    ).all()
    return [_period_view(item) for item in items]


@router.post(
    "/periods",
    response_model=PayrollPeriodView,
    status_code=status.HTTP_201_CREATED,
)
def create_period(
    organization_id: UUID,
    payload: PayrollPeriodCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollPeriodView:
    try:
        item = PayrollService(session).create_period(
            organization_id=organization_id,
            code=payload.code,
            label=payload.label,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            attendance_calculation_version=payload.attendance_calculation_version,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _period_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/periods/{period_id}/lock", response_model=PayrollPeriodView)
def lock_period(
    organization_id: UUID,
    period_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollPeriodView:
    try:
        item = PayrollService(session).lock_period(
            organization_id=organization_id,
            period_id=period_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _period_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/periods/{period_id}/close", response_model=PayrollPeriodView)
def close_period(
    organization_id: UUID,
    period_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollPeriodView:
    try:
        item = PayrollService(session).close_period(
            organization_id=organization_id,
            period_id=period_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _period_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/runs", response_model=list[PayrollRunView])
def list_runs(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PayrollRunView]:
    items = session.scalars(
        select(PayrollRun)
        .where(PayrollRun.organization_id == organization_id)
        .order_by(PayrollRun.created_at.desc())
    ).all()
    return [_run_view(item) for item in items]


@router.post(
    "/runs",
    response_model=PayrollRunView,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    organization_id: UUID,
    payload: PayrollRunCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    try:
        item = PayrollService(session).create_run(
            organization_id=organization_id,
            period_id=payload.period_id,
            calculation_version=payload.calculation_version,
            policy_snapshot=payload.policy_snapshot,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _run_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post(
    "/runs/{run_id}/lines",
    response_model=PayrollLineView,
    status_code=status.HTTP_201_CREATED,
)
def add_line(
    organization_id: UUID,
    run_id: UUID,
    payload: PayrollLineCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollLineView:
    try:
        item = PayrollService(session).add_line(
            organization_id=organization_id,
            run_id=run_id,
            employee_id=payload.employee_id,
            gross_amount=payload.gross_amount,
            deduction_amount=payload.deduction_amount,
            tax_amount=payload.tax_amount,
            employee_snapshot=payload.employee_snapshot,
            attendance_snapshot=payload.attendance_snapshot,
            earnings_snapshot=payload.earnings_snapshot,
            deductions_snapshot=payload.deductions_snapshot,
            explanation=payload.explanation,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _line_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/runs/{run_id}/lines", response_model=list[PayrollLineView])
def list_lines(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PayrollLineView]:
    run = session.get(PayrollRun, run_id)
    if not run or run.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payroll run not found")
    items = session.scalars(
        select(PayrollLine)
        .where(PayrollLine.run_id == run_id)
        .order_by(PayrollLine.employee_id)
    ).all()
    return [_line_view(item) for item in items]


def _transition(
    *,
    session: Session,
    organization_id: UUID,
    run_id: UUID,
    identity: RequestIdentity,
    action: str,
) -> PayrollRunView:
    service = PayrollService(session)
    method = getattr(service, action)
    try:
        item = method(
            organization_id=organization_id,
            run_id=run_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _run_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/runs/{run_id}/submit", response_model=PayrollRunView)
def submit_run(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    return _transition(
        session=session,
        organization_id=organization_id,
        run_id=run_id,
        identity=identity,
        action="submit_run",
    )


@router.post("/runs/{run_id}/approve", response_model=PayrollRunView)
def approve_run(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    return _transition(
        session=session,
        organization_id=organization_id,
        run_id=run_id,
        identity=identity,
        action="approve_run",
    )


@router.post("/runs/{run_id}/post", response_model=PayrollRunView)
def post_run(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    return _transition(
        session=session,
        organization_id=organization_id,
        run_id=run_id,
        identity=identity,
        action="post_run",
    )


@router.post("/runs/{run_id}/reversal-request", response_model=PayrollRunView)
def request_reversal(
    organization_id: UUID,
    run_id: UUID,
    payload: ReversalRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    try:
        item = PayrollService(session).request_reversal(
            organization_id=organization_id,
            run_id=run_id,
            actor_user_id=identity.principal.user.id,
            reason=payload.reason,
            grants=identity.principal.grants,
        )
        _commit(session)
        return _run_view(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/runs/{run_id}/reversal-approve", response_model=PayrollRunView)
def approve_reversal(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollRunView:
    return _transition(
        session=session,
        organization_id=organization_id,
        run_id=run_id,
        identity=identity,
        action="approve_reversal",
    )


@router.get("/runs/{run_id}/history", response_model=list[PayrollHistoryView])
def run_history(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[PayrollHistoryView]:
    run = session.get(PayrollRun, run_id)
    if not run or run.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payroll run not found")
    items = session.scalars(
        select(PayrollHistory)
        .where(
            PayrollHistory.organization_id == organization_id,
            PayrollHistory.run_id == run_id,
        )
        .order_by(PayrollHistory.occurred_at, PayrollHistory.id)
    ).all()
    return [
        PayrollHistoryView(
            id=item.id,
            run_id=item.run_id,
            actor_user_id=item.actor_user_id,
            action=item.action,
            reason=item.reason,
            snapshot=item.snapshot,
            occurred_at=item.occurred_at,
        )
        for item in items
    ]


@router.get("/runs/{run_id}/export", response_model=list[dict[str, str]])
def export_run(
    organization_id: UUID,
    run_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.export")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[dict[str, str]]:
    try:
        rows = PayrollService(session).export_rows(
            organization_id=organization_id,
            run_id=run_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        _commit(session)
        return rows
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc
