import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_organization_permission,
)
from hajiriflow.db.models.payroll import PayrollLine, PayrollPeriod, PayrollRun
from hajiriflow.db.models.workforce_profile import CompanyReportProfile
from hajiriflow.reporting.exports import pdf_bytes, printable_html, workbook_bytes
from hajiriflow.reporting.matrix import range_register
from hajiriflow.reporting.service import AttendanceReportingService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/reports",
    tags=["reports"],
)


class AttendanceEventView(BaseModel):
    id: UUID
    employee_id: UUID | None
    source: str
    device_id: UUID | None
    occurred_at: datetime
    event_type: str
    verification_method: str | None
    source_fingerprint: str | None
    manual_status: str | None


class DailyAttendanceRow(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    work_date: date
    status: str
    base_status: str
    check_in_at: datetime | None
    check_out_at: datetime | None
    worked_minutes: int
    late_minutes: int
    planned_minutes: int
    early_arrival_minutes: int
    early_departure_minutes: int
    late_departure_minutes: int
    regular_overtime_minutes: int
    holiday_overtime_minutes: int
    source_event_count: int
    calculation_version: str | None
    source_revision: int | None
    explanation_trace: list[dict]


class DepartmentCoverageRow(BaseModel):
    department_id: UUID | None
    department_name: str
    employee_count: int
    coverage_count: int
    coverage_percent: float
    status_counts: dict[str, int]
    employee_ids: list[UUID]


class EmployeeAttendanceDetail(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    from_date: date
    to_date: date
    status_counts: dict[str, int]
    present_days: int
    partial_days: int
    absent_days: int
    leave_days: int
    field_duty_days: int
    holiday_days: int
    weekly_off_days: int
    uncalculated_days: int
    worked_minutes: int
    late_minutes: int
    regular_overtime_minutes: int
    holiday_overtime_minutes: int
    records: list[DailyAttendanceRow]


class WorkforceAttendanceSummary(BaseModel):
    from_date: date
    to_date: date
    employee_count: int
    calculated_records: int
    present_records: int
    partial_records: int
    absent_records: int
    leave_records: int
    field_duty_records: int
    holiday_records: int
    weekly_off_records: int
    uncalculated_records: int
    worked_minutes: int
    late_minutes: int
    regular_overtime_minutes: int
    holiday_overtime_minutes: int


class MonthlyWorkforceRow(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    status_counts: dict[str, int]
    worked_minutes: int
    late_minutes: int
    regular_overtime_minutes: int
    holiday_overtime_minutes: int


class HajiriRegisterRow(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    days: dict[str, str]
    codes: dict[str, str]
    status_counts: dict[str, int]
    present_days: int
    partial_days: int
    absent_days: int


class BsHajiriRegister(BaseModel):
    bs_year: int
    bs_month: int
    month_name: str
    days_in_month: int
    first_ad_date: date
    last_ad_date: date
    rows: list[dict]


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


def _bad_request(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _daily_view(row: dict[str, object]) -> DailyAttendanceRow:
    return DailyAttendanceRow(
        employee_id=row["employee_id"],
        employee_code=str(row["employee_code"]),
        employee_name=str(row["employee_name"]),
        work_date=row["work_date"],
        status=str(row["day_status"]),
        base_status=str(row["base_status"]),
        check_in_at=row["check_in_at"],
        check_out_at=row["check_out_at"],
        worked_minutes=int(row["worked_minutes"]),
        late_minutes=int(row["late_minutes"]),
        planned_minutes=int(row["planned_minutes"]),
        early_arrival_minutes=int(row["early_arrival_minutes"]),
        early_departure_minutes=int(row["early_departure_minutes"]),
        late_departure_minutes=int(row["late_departure_minutes"]),
        regular_overtime_minutes=int(row["regular_overtime_minutes"]),
        holiday_overtime_minutes=int(row["holiday_overtime_minutes"]),
        source_event_count=int(row["source_event_count"]),
        calculation_version=(
            str(row["engine_version"]) if row["engine_version"] is not None else None
        ),
        source_revision=row["source_revision"],
        explanation_trace=list(row["explanation_trace"]),
    )


def _detail_view(detail: dict[str, object]) -> EmployeeAttendanceDetail:
    counts = defaultdict(int, detail["status_counts"])
    return EmployeeAttendanceDetail(
        employee_id=detail["employee_id"],
        employee_code=str(detail["employee_code"]),
        employee_name=str(detail["employee_name"]),
        from_date=detail["from_date"],
        to_date=detail["to_date"],
        status_counts=dict(counts),
        present_days=counts["present"],
        partial_days=counts["partial"],
        absent_days=counts["absent"],
        leave_days=counts["leave"],
        field_duty_days=counts["field_duty"],
        holiday_days=counts["holiday"],
        weekly_off_days=counts["weekly_off"],
        uncalculated_days=counts["uncalculated"],
        worked_minutes=int(detail["worked_minutes"]),
        late_minutes=int(detail["late_minutes"]),
        regular_overtime_minutes=int(detail["regular_overtime_minutes"]),
        holiday_overtime_minutes=int(detail["holiday_overtime_minutes"]),
        records=[_daily_view(row) for row in detail["records"]],
    )


def _report_metadata(session: Session, organization_id: UUID) -> list[tuple[str, object]]:
    service = AttendanceReportingService(session)
    company = service.company(organization_id)
    profile = session.get(CompanyReportProfile, organization_id)
    metadata: list[tuple[str, object]] = [("Organization", company.display_name)]
    if profile is not None:
        if profile.report_header:
            metadata.append(("Report header", profile.report_header))
        if profile.address:
            metadata.append(("Address", profile.address))
        if profile.phone:
            metadata.append(("Phone", profile.phone))
    return metadata


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
    device_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AttendanceEventView]:
    try:
        rows = AttendanceReportingService(session).attendance_events(
            organization_id=organization_id,
            from_at=from_at,
            to_at=to_at,
            employee_id=employee_id,
            device_id=device_id,
            limit=limit,
            offset=offset,
        )
        return [AttendanceEventView(**row) for row in rows]
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.get("/employees/{employee_id}/events", response_model=list[AttendanceEventView])
def employee_event_drilldown(
    organization_id: UUID,
    employee_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[AttendanceEventView]:
    try:
        rows = AttendanceReportingService(session).employee_day_events(
            organization_id=organization_id,
            employee_id=employee_id,
            work_date=work_date,
        )
        return [AttendanceEventView(**row) for row in rows]
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


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
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[DailyAttendanceRow]:
    try:
        rows = AttendanceReportingService(session).daily_rows(
            organization_id=organization_id,
            work_date=work_date,
            limit=limit,
            offset=offset,
        )
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc
    if only_absent:
        rows = [row for row in rows if row["day_status"] == "absent"]
    return [_daily_view(row) for row in rows]


@router.get("/daily-absence", response_model=list[DailyAttendanceRow])
def daily_absence_report(
    organization_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[DailyAttendanceRow]:
    try:
        rows = AttendanceReportingService(session).daily_rows(
            organization_id=organization_id,
            work_date=work_date,
            limit=limit,
            offset=offset,
        )
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return [_daily_view(row) for row in rows if row["day_status"] == "absent"]


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
    try:
        rows = AttendanceReportingService(session).department_coverage(
            organization_id=organization_id,
            work_date=work_date,
        )
        return [DepartmentCoverageRow(**row) for row in rows]
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


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
    try:
        detail = AttendanceReportingService(session).employee_detail(
            organization_id=organization_id,
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
        )
        return _detail_view(detail)
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


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
    try:
        service = AttendanceReportingService(session)
        service.validate_range(from_date, to_date, max_days=62)
        rows = service.monthly_summary(
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=1000,
        )
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for key, value in row["status_counts"].items():
            counts[key] += int(value)
    uncalculated = counts["uncalculated"]
    calculated = sum(counts.values()) - uncalculated
    return WorkforceAttendanceSummary(
        from_date=from_date,
        to_date=to_date,
        employee_count=len(rows),
        calculated_records=calculated,
        present_records=counts["present"],
        partial_records=counts["partial"],
        absent_records=counts["absent"],
        leave_records=counts["leave"],
        field_duty_records=counts["field_duty"],
        holiday_records=counts["holiday"],
        weekly_off_records=counts["weekly_off"],
        uncalculated_records=uncalculated,
        worked_minutes=sum(int(row["worked_minutes"]) for row in rows),
        late_minutes=sum(int(row["late_minutes"]) for row in rows),
        regular_overtime_minutes=sum(
            int(row["regular_overtime_minutes"]) for row in rows
        ),
        holiday_overtime_minutes=sum(
            int(row["holiday_overtime_minutes"]) for row in rows
        ),
    )


@router.get("/monthly-summary", response_model=list[MonthlyWorkforceRow])
def monthly_workforce_summary(
    organization_id: UUID,
    from_date: date,
    to_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[MonthlyWorkforceRow]:
    try:
        rows = AttendanceReportingService(session).monthly_summary(
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return [MonthlyWorkforceRow(**row) for row in rows]
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


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
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[HajiriRegisterRow]:
    try:
        rows = range_register(
            AttendanceReportingService(session),
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc
    output = []
    for row in rows:
        counts = defaultdict(int, row["status_counts"])
        output.append(
            HajiriRegisterRow(
                employee_id=row["employee_id"],
                employee_code=str(row["employee_code"]),
                employee_name=str(row["employee_name"]),
                days=dict(row["days"]),
                codes=dict(row["codes"]),
                status_counts=dict(counts),
                present_days=counts["present"],
                partial_days=counts["partial"],
                absent_days=counts["absent"],
            )
        )
    return output


@router.get("/hajiri-register/bs", response_model=BsHajiriRegister)
def bs_hajiri_register(
    organization_id: UUID,
    bs_year: int,
    bs_month: int,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> BsHajiriRegister:
    try:
        item = AttendanceReportingService(session).hajiri_register(
            organization_id=organization_id,
            bs_year=bs_year,
            bs_month=bs_month,
            limit=limit,
            offset=offset,
        )
        return BsHajiriRegister(**item)
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.get("/self/attendance", response_model=EmployeeAttendanceDetail)
def own_attendance_detail(
    organization_id: UUID,
    from_date: date,
    to_date: date,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeAttendanceDetail:
    employee_id = identity.principal.user.employee_id
    if employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="web account is not linked to an employee",
        )
    try:
        return _detail_view(
            AttendanceReportingService(session).employee_detail(
                organization_id=organization_id,
                employee_id=employee_id,
                from_date=from_date,
                to_date=to_date,
            )
        )
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.get("/self/attendance/{work_date}/events", response_model=list[AttendanceEventView])
def own_attendance_events(
    organization_id: UUID,
    work_date: date,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[AttendanceEventView]:
    employee_id = identity.principal.user.employee_id
    if employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="web account is not linked to an employee",
        )
    try:
        rows = AttendanceReportingService(session).employee_day_events(
            organization_id=organization_id,
            employee_id=employee_id,
            work_date=work_date,
        )
        return [AttendanceEventView(**row) for row in rows]
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


def _export_table(
    *,
    report_name: str,
    service: AttendanceReportingService,
    organization_id: UUID,
    work_date: date | None,
    from_date: date | None,
    to_date: date | None,
    employee_id: UUID | None,
    bs_year: int | None,
    bs_month: int | None,
) -> tuple[str, list[str], list[list[object]], list[tuple[str, object]], bool]:
    if report_name in {"daily", "absence"}:
        if work_date is None:
            raise ValueError("work_date is required for daily exports")
        rows = service.daily_rows(
            organization_id=organization_id,
            work_date=work_date,
            limit=1000,
        )
        if report_name == "absence":
            rows = [row for row in rows if row["day_status"] == "absent"]
        headers = [
            "Employee code",
            "Employee name",
            "Date",
            "Status",
            "Check in",
            "Check out",
            "Worked min",
            "Late min",
            "Regular OT",
            "Holiday OT",
            "Events",
            "Engine",
        ]
        values = [
            [
                row["employee_code"],
                row["employee_name"],
                row["work_date"],
                row["day_status"],
                row["check_in_at"],
                row["check_out_at"],
                row["worked_minutes"],
                row["late_minutes"],
                row["regular_overtime_minutes"],
                row["holiday_overtime_minutes"],
                row["source_event_count"],
                row["engine_version"],
            ]
            for row in rows
        ]
        return report_name.title(), headers, values, [("Date", work_date)], False

    if report_name == "department":
        if work_date is None:
            raise ValueError("work_date is required for department export")
        rows = service.department_coverage(
            organization_id=organization_id,
            work_date=work_date,
        )
        headers = ["Department", "Employees", "Coverage", "Coverage %", "Statuses"]
        values = [
            [
                row["department_name"],
                row["employee_count"],
                row["coverage_count"],
                row["coverage_percent"],
                json.dumps(row["status_counts"], sort_keys=True),
            ]
            for row in rows
        ]
        return "Department coverage", headers, values, [("Date", work_date)], False

    if report_name == "employee":
        if employee_id is None or from_date is None or to_date is None:
            raise ValueError("employee_id, from_date and to_date are required")
        detail = service.employee_detail(
            organization_id=organization_id,
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
        )
        headers = [
            "Date",
            "Status",
            "Check in",
            "Check out",
            "Worked min",
            "Late min",
            "Regular OT",
            "Holiday OT",
            "Events",
        ]
        values = [
            [
                row["work_date"],
                row["day_status"],
                row["check_in_at"],
                row["check_out_at"],
                row["worked_minutes"],
                row["late_minutes"],
                row["regular_overtime_minutes"],
                row["holiday_overtime_minutes"],
                row["source_event_count"],
            ]
            for row in detail["records"]
        ]
        metadata = [
            ("Employee", detail["employee_name"]),
            ("Employee code", detail["employee_code"]),
            ("From", from_date),
            ("To", to_date),
        ]
        return "Employee attendance detail", headers, values, metadata, False

    if report_name == "monthly":
        if from_date is None or to_date is None:
            raise ValueError("from_date and to_date are required for monthly export")
        rows = service.monthly_summary(
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=1000,
        )
        headers = [
            "Employee code",
            "Employee name",
            "Statuses",
            "Worked min",
            "Late min",
            "Regular OT",
            "Holiday OT",
        ]
        values = [
            [
                row["employee_code"],
                row["employee_name"],
                json.dumps(row["status_counts"], sort_keys=True),
                row["worked_minutes"],
                row["late_minutes"],
                row["regular_overtime_minutes"],
                row["holiday_overtime_minutes"],
            ]
            for row in rows
        ]
        return "Monthly workforce summary", headers, values, [("From", from_date), ("To", to_date)], False

    if report_name == "hajiri":
        if bs_year is None or bs_month is None:
            raise ValueError("bs_year and bs_month are required for Hajiri export")
        register = service.hajiri_register(
            organization_id=organization_id,
            bs_year=bs_year,
            bs_month=bs_month,
            limit=1000,
        )
        days = list(range(1, int(register["days_in_month"]) + 1))
        headers = ["Employee code", "Employee name", *[str(day) for day in days], "Totals"]
        values = [
            [
                row["employee_code"],
                row["employee_name"],
                *[row["days"].get(str(day), "") for day in days],
                json.dumps(row["status_counts"], sort_keys=True),
            ]
            for row in register["rows"]
        ]
        metadata = [
            ("BS year", bs_year),
            ("BS month", bs_month),
            ("Month", register["month_name"]),
            ("AD range", f"{register['first_ad_date']} to {register['last_ad_date']}"),
        ]
        return "Hajiri register", headers, values, metadata, True

    if report_name == "events":
        rows = service.attendance_events(
            organization_id=organization_id,
            limit=1000,
        )
        headers = [
            "ID",
            "Employee",
            "Source",
            "Device",
            "Occurred at",
            "Type",
            "Verification",
            "Fingerprint",
            "Manual status",
        ]
        values = [
            [
                row["id"],
                row["employee_id"],
                row["source"],
                row["device_id"],
                row["occurred_at"],
                row["event_type"],
                row["verification_method"],
                row["source_fingerprint"],
                row["manual_status"],
            ]
            for row in rows
        ]
        return "Attendance event explorer", headers, values, [], False

    raise ValueError("unsupported report export")


@router.get("/exports/{report_name}")
def export_report(
    organization_id: UUID,
    report_name: Literal["daily", "absence", "department", "employee", "monthly", "hajiri", "events"],
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("attendance.export")),
    ],
    session: Annotated[Session, Depends(get_db)],
    export_format: Literal["xlsx", "pdf", "html"] = Query(alias="format"),
    work_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    employee_id: UUID | None = None,
    bs_year: int | None = None,
    bs_month: int | None = None,
) -> Response:
    service = AttendanceReportingService(session)
    try:
        title, headers, rows, metadata, a3 = _export_table(
            report_name=report_name,
            service=service,
            organization_id=organization_id,
            work_date=work_date,
            from_date=from_date,
            to_date=to_date,
            employee_id=employee_id,
            bs_year=bs_year,
            bs_month=bs_month,
        )
        metadata = [*_report_metadata(session, organization_id), *metadata]
        filename = f"hajiriflow-{report_name}"
        if export_format == "xlsx":
            content = workbook_bytes(
                title=title,
                headers=headers,
                rows=rows,
                metadata=metadata,
            )
            return Response(
                content=content,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}.xlsx"'
                },
            )
        if export_format == "pdf":
            content = pdf_bytes(
                title=title,
                headers=headers,
                rows=rows,
                metadata=metadata,
                a3_landscape=a3,
            )
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}.pdf"'
                },
            )
        content = printable_html(
            title=title,
            headers=headers,
            rows=rows,
            metadata=metadata,
            a3_landscape=a3,
        )
        return Response(content=content, media_type="text/html; charset=utf-8")
    except (LookupError, ValueError) as exc:
        raise _bad_request(exc) from exc


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
