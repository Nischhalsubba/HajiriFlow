from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_organization_permission,
)
from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.device import (
    DeviceEmployeeMapping,
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.payroll import PayrollLine, PayrollPeriod, PayrollRun
from hajiriflow.db.models.workforce import (
    Employee,
    EmployeeOrganizationAssignment,
    OrganizationNode,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/reports",
    tags=["reports"],
)


class AttendanceEventView(BaseModel):
    id: UUID
    employee_id: UUID | None
    device_id: UUID
    occurred_at: datetime
    received_at: datetime
    punch_kind: str
    verification_method: str | None
    source_fingerprint: str


class DailyAttendanceRow(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    status: str
    check_in_at: datetime | None
    check_out_at: datetime | None
    worked_minutes: int
    late_minutes: int
    calculation_version: str | None
    source_revision: int | None


class DepartmentCoverageRow(BaseModel):
    department_id: UUID | None
    department_name: str
    employee_count: int
    present: int
    partial: int
    absent: int
    uncalculated: int


class EmployeeAttendanceDetail(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    from_date: date
    to_date: date
    present_days: int
    partial_days: int
    absent_days: int
    uncalculated_days: int
    worked_minutes: int
    late_minutes: int
    records: list[DailyAttendanceRow]


class WorkforceAttendanceSummary(BaseModel):
    from_date: date
    to_date: date
    employee_count: int
    calculated_records: int
    present_records: int
    partial_records: int
    absent_records: int
    worked_minutes: int
    late_minutes: int


class HajiriRegisterRow(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    days: dict[str, str]
    present_days: int
    partial_days: int
    absent_days: int


class PayrollWorksheetRow(BaseModel):
    employee_id: UUID
    employee_snapshot: dict
    attendance_snapshot: dict
    earnings_snapshot: dict
    deductions_snapshot: dict
    gross_amount: Decimal
    deduction_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    direction: str
    currency: str


class PayrollWorksheet(BaseModel):
    run_id: UUID
    period_id: UUID
    period_code: str
    period_label: str
    run_status: str
    calculation_version: str
    attendance_calculation_version: str
    rows: list[PayrollWorksheetRow]


def _date_range(from_date: date, to_date: date, *, max_days: int = 366) -> None:
    if to_date < from_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="to_date must be on or after from_date",
        )
    if (to_date - from_date).days + 1 > max_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"report range cannot exceed {max_days} days",
        )


def _active_employees(session: Session, organization_id: UUID) -> list[Employee]:
    return list(
        session.scalars(
            select(Employee)
            .where(
                Employee.organization_id == organization_id,
                Employee.status == "active",
            )
            .order_by(Employee.employee_code)
        ).all()
    )


def _record_row(employee: Employee, item: AttendanceRecord | None) -> DailyAttendanceRow:
    return DailyAttendanceRow(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=employee.display_name,
        status=item.status if item else "uncalculated",
        check_in_at=item.check_in_at if item else None,
        check_out_at=item.check_out_at if item else None,
        worked_minutes=item.worked_minutes if item else 0,
        late_minutes=item.late_minutes if item else 0,
        calculation_version=item.calculation_version if item else None,
        source_revision=item.source_revision if item else None,
    )


def _department_for_employee(
    session: Session,
    *,
    organization_id: UUID,
    employee_id: UUID,
    observed_on: date,
) -> OrganizationNode | None:
    assignment = session.scalar(
        select(EmployeeOrganizationAssignment)
        .where(
            EmployeeOrganizationAssignment.organization_id == organization_id,
            EmployeeOrganizationAssignment.employee_id == employee_id,
            EmployeeOrganizationAssignment.is_primary.is_(True),
            EmployeeOrganizationAssignment.starts_on <= observed_on,
            or_(
                EmployeeOrganizationAssignment.ends_on.is_(None),
                EmployeeOrganizationAssignment.ends_on >= observed_on,
            ),
        )
        .order_by(EmployeeOrganizationAssignment.starts_on.desc())
        .limit(1)
    )
    if assignment is None:
        return None
    node = session.get(OrganizationNode, assignment.organization_node_id)
    visited: set[UUID] = set()
    while node is not None and node.id not in visited:
        visited.add(node.id)
        if node.node_type == "department":
            return node
        node = session.get(OrganizationNode, node.parent_id) if node.parent_id else None
    return None


@router.get("/attendance-events", response_model=list[AttendanceEventView])
def attendance_event_explorer(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    employee_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AttendanceEventView]:
    query = (
        select(RawPunch, DeviceEmployeeMapping.employee_id)
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
        .where(RawPunch.organization_id == organization_id)
    )
    if from_at is not None:
        query = query.where(RawPunch.occurred_at >= from_at)
    if to_at is not None:
        query = query.where(RawPunch.occurred_at <= to_at)
    if employee_id is not None:
        query = query.where(DeviceEmployeeMapping.employee_id == employee_id)
    rows = session.execute(
        query.order_by(RawPunch.occurred_at.desc()).limit(limit)
    ).all()
    return [
        AttendanceEventView(
            id=punch.id,
            employee_id=mapped_employee_id,
            device_id=punch.device_id,
            occurred_at=punch.occurred_at,
            received_at=punch.received_at,
            punch_kind=punch.punch_kind,
            verification_method=punch.verification_method,
            source_fingerprint=punch.source_fingerprint,
        )
        for punch, mapped_employee_id in rows
    ]


@router.get("/daily", response_model=list[DailyAttendanceRow])
def daily_workforce_status(
    organization_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    only_absent: bool = False,
) -> list[DailyAttendanceRow]:
    employees = _active_employees(session, organization_id)
    records = {
        item.employee_id: item
        for item in session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.work_date == work_date,
            )
        ).all()
    }
    rows = [_record_row(employee, records.get(employee.id)) for employee in employees]
    if only_absent:
        rows = [row for row in rows if row.status == "absent"]
    return rows


@router.get("/department-coverage", response_model=list[DepartmentCoverageRow])
def department_coverage(
    organization_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DepartmentCoverageRow]:
    employees = _active_employees(session, organization_id)
    records = {
        item.employee_id: item
        for item in session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.work_date == work_date,
            )
        ).all()
    }
    grouped: dict[tuple[UUID | None, str], dict[str, int]] = defaultdict(
        lambda: {
            "employee_count": 0,
            "present": 0,
            "partial": 0,
            "absent": 0,
            "uncalculated": 0,
        }
    )
    for employee in employees:
        department = _department_for_employee(
            session,
            organization_id=organization_id,
            employee_id=employee.id,
            observed_on=work_date,
        )
        key = (
            department.id if department else None,
            department.name if department else "Unassigned",
        )
        bucket = grouped[key]
        bucket["employee_count"] += 1
        record = records.get(employee.id)
        bucket[record.status if record else "uncalculated"] += 1

    return [
        DepartmentCoverageRow(
            department_id=department_id,
            department_name=department_name,
            **counts,
        )
        for (department_id, department_name), counts in sorted(
            grouped.items(), key=lambda item: item[0][1].casefold()
        )
    ]


@router.get(
    "/employees/{employee_id}/detail",
    response_model=EmployeeAttendanceDetail,
)
def employee_attendance_detail(
    organization_id: UUID,
    employee_id: UUID,
    from_date: date,
    to_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeAttendanceDetail:
    _date_range(from_date, to_date)
    employee = session.get(Employee, employee_id)
    if not employee or employee.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="employee not found",
        )
    records = list(
        session.scalars(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.work_date >= from_date,
                AttendanceRecord.work_date <= to_date,
            )
            .order_by(AttendanceRecord.work_date)
        ).all()
    )
    by_date = {item.work_date: item for item in records}
    rows: list[DailyAttendanceRow] = []
    cursor = from_date
    while cursor <= to_date:
        rows.append(_record_row(employee, by_date.get(cursor)))
        cursor += timedelta(days=1)
    return EmployeeAttendanceDetail(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=employee.display_name,
        from_date=from_date,
        to_date=to_date,
        present_days=sum(item.status == "present" for item in rows),
        partial_days=sum(item.status == "partial" for item in rows),
        absent_days=sum(item.status == "absent" for item in rows),
        uncalculated_days=sum(item.status == "uncalculated" for item in rows),
        worked_minutes=sum(item.worked_minutes for item in rows),
        late_minutes=sum(item.late_minutes for item in rows),
        records=rows,
    )


@router.get("/summary", response_model=WorkforceAttendanceSummary)
def workforce_attendance_summary(
    organization_id: UUID,
    from_date: date,
    to_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> WorkforceAttendanceSummary:
    _date_range(from_date, to_date)
    employees = _active_employees(session, organization_id)
    records = list(
        session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.work_date >= from_date,
                AttendanceRecord.work_date <= to_date,
            )
        ).all()
    )
    return WorkforceAttendanceSummary(
        from_date=from_date,
        to_date=to_date,
        employee_count=len(employees),
        calculated_records=len(records),
        present_records=sum(item.status == "present" for item in records),
        partial_records=sum(item.status == "partial" for item in records),
        absent_records=sum(item.status == "absent" for item in records),
        worked_minutes=sum(item.worked_minutes for item in records),
        late_minutes=sum(item.late_minutes for item in records),
    )


@router.get("/hajiri-register", response_model=list[HajiriRegisterRow])
def hajiri_register(
    organization_id: UUID,
    from_date: date,
    to_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[HajiriRegisterRow]:
    _date_range(from_date, to_date, max_days=62)
    employees = _active_employees(session, organization_id)
    records = list(
        session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.work_date >= from_date,
                AttendanceRecord.work_date <= to_date,
            )
        ).all()
    )
    lookup = {(item.employee_id, item.work_date): item for item in records}
    rows: list[HajiriRegisterRow] = []
    for employee in employees:
        days: dict[str, str] = {}
        present = partial = absent = 0
        cursor = from_date
        while cursor <= to_date:
            record = lookup.get((employee.id, cursor))
            value = record.status if record else "uncalculated"
            days[cursor.isoformat()] = value
            present += int(value == "present")
            partial += int(value == "partial")
            absent += int(value == "absent")
            cursor += timedelta(days=1)
        rows.append(
            HajiriRegisterRow(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                employee_name=employee.display_name,
                days=days,
                present_days=present,
                partial_days=partial,
                absent_days=absent,
            )
        )
    return rows


@router.get("/payroll/{run_id}/worksheet", response_model=PayrollWorksheet)
def attendance_to_salary_worksheet(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollWorksheet:
    run = session.get(PayrollRun, run_id)
    if not run or run.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payroll run not found",
        )
    period = session.get(PayrollPeriod, run.period_id)
    if period is None or period.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payroll period not found",
        )
    lines = session.scalars(
        select(PayrollLine)
        .where(PayrollLine.run_id == run_id)
        .order_by(PayrollLine.employee_id)
    ).all()
    return PayrollWorksheet(
        run_id=run.id,
        period_id=period.id,
        period_code=period.code,
        period_label=period.label,
        run_status=run.status,
        calculation_version=run.calculation_version,
        attendance_calculation_version=period.attendance_calculation_version,
        rows=[
            PayrollWorksheetRow(
                employee_id=line.employee_id,
                employee_snapshot=line.employee_snapshot,
                attendance_snapshot=line.attendance_snapshot,
                earnings_snapshot=line.earnings_snapshot,
                deductions_snapshot=line.deductions_snapshot,
                gross_amount=line.gross_amount,
                deduction_amount=line.deduction_amount,
                tax_amount=line.tax_amount,
                net_amount=line.net_amount,
                direction=line.direction,
                currency=line.currency,
            )
            for line in lines
        ],
    )
