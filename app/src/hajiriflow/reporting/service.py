from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hajiriflow.calendar_leave.bs_dates import BsDateService
from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import (
    AttendanceRecordDetail,
    ManualAttendanceEvent,
)
from hajiriflow.db.models.calendar_leave import (
    FieldDutyRequest,
    Holiday,
    LeaveRequest,
    OrganizationCalendarSettings,
)
from hajiriflow.db.models.device import DeviceEmployeeMapping, DeviceUser, RawPunch
from hajiriflow.db.models.workforce import (
    CompanyProfile,
    Employee,
    EmployeeOrganizationAssignment,
    OrganizationNode,
)

MAX_REPORT_EMPLOYEES = 2000
MAX_REPORT_DAYS = 366
MAX_MATRIX_DAYS = 62
DEFAULT_WEEKENDS = [5]

STATUS_CODES = {
    "present": "P",
    "partial": "PT",
    "absent": "A",
    "leave": "L",
    "field_duty": "FD",
    "holiday": "H",
    "weekly_off": "WO",
    "uncalculated": "U",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AttendanceReportingService:
    """Read-only reporting over the canonical attendance-v2 result model."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def company(self, organization_id: UUID) -> CompanyProfile:
        company = self.session.get(CompanyProfile, organization_id)
        if company is None:
            raise LookupError("organization not found")
        return company

    @staticmethod
    def validate_range(
        from_date: date,
        to_date: date,
        *,
        max_days: int = MAX_REPORT_DAYS,
    ) -> None:
        if to_date < from_date:
            raise ValueError("to_date must be on or after from_date")
        days = (to_date - from_date).days + 1
        if days > max_days:
            raise ValueError(f"report range cannot exceed {max_days} days")

    def employees(
        self,
        *,
        organization_id: UUID,
        from_date: date,
        to_date: date,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Employee]:
        self.validate_range(from_date, to_date)
        if limit < 1 or limit > 1000:
            raise ValueError("employee page size must be between 1 and 1000")
        if offset < 0:
            raise ValueError("employee offset cannot be negative")
        query = (
            select(Employee)
            .where(
                Employee.organization_id == organization_id,
                Employee.joined_on <= to_date,
                or_(Employee.left_on.is_(None), Employee.left_on >= from_date),
            )
            .order_by(Employee.employee_code, Employee.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(query).all())

    def all_employees_bounded(
        self,
        *,
        organization_id: UUID,
        observed_on: date,
    ) -> list[Employee]:
        items = list(
            self.session.scalars(
                select(Employee)
                .where(
                    Employee.organization_id == organization_id,
                    Employee.joined_on <= observed_on,
                    or_(Employee.left_on.is_(None), Employee.left_on >= observed_on),
                )
                .order_by(Employee.employee_code, Employee.id)
                .limit(MAX_REPORT_EMPLOYEES + 1)
            ).all()
        )
        if len(items) > MAX_REPORT_EMPLOYEES:
            raise ValueError(
                f"organization report exceeds the {MAX_REPORT_EMPLOYEES} employee bound"
            )
        return items

    def _records(
        self,
        *,
        organization_id: UUID,
        employee_ids: list[UUID],
        from_date: date,
        to_date: date,
    ) -> dict[tuple[UUID, date], tuple[AttendanceRecord, AttendanceRecordDetail | None]]:
        if not employee_ids:
            return {}
        rows = self.session.execute(
            select(AttendanceRecord, AttendanceRecordDetail)
            .outerjoin(
                AttendanceRecordDetail,
                AttendanceRecordDetail.attendance_record_id == AttendanceRecord.id,
            )
            .where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.work_date >= from_date,
                AttendanceRecord.work_date <= to_date,
            )
        ).all()
        return {
            (record.employee_id, record.work_date): (record, detail)
            for record, detail in rows
        }

    def _range_context(
        self,
        *,
        organization_id: UUID,
        employee_ids: list[UUID],
        from_date: date,
        to_date: date,
    ) -> dict[str, object]:
        settings = self.session.get(OrganizationCalendarSettings, organization_id)
        weekend_weekdays = set(
            settings.weekend_weekdays if settings else DEFAULT_WEEKENDS
        )
        holidays = {
            item.holiday_date: item
            for item in self.session.scalars(
                select(Holiday).where(
                    Holiday.organization_id == organization_id,
                    Holiday.status == "active",
                    Holiday.category != "optional",
                    Holiday.holiday_date >= from_date,
                    Holiday.holiday_date <= to_date,
                )
            ).all()
        }
        if employee_ids:
            leave_items = self.session.scalars(
                select(LeaveRequest).where(
                    LeaveRequest.organization_id == organization_id,
                    LeaveRequest.employee_id.in_(employee_ids),
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= to_date,
                    LeaveRequest.end_date >= from_date,
                )
            ).all()
            field_items = self.session.scalars(
                select(FieldDutyRequest).where(
                    FieldDutyRequest.organization_id == organization_id,
                    FieldDutyRequest.employee_id.in_(employee_ids),
                    FieldDutyRequest.status == "approved",
                    FieldDutyRequest.start_date <= to_date,
                    FieldDutyRequest.end_date >= from_date,
                )
            ).all()
        else:
            leave_items = []
            field_items = []
        leaves: dict[UUID, list[LeaveRequest]] = defaultdict(list)
        duties: dict[UUID, list[FieldDutyRequest]] = defaultdict(list)
        for item in leave_items:
            leaves[item.employee_id].append(item)
        for item in field_items:
            duties[item.employee_id].append(item)
        return {
            "weekends": weekend_weekdays,
            "holidays": holidays,
            "leaves": leaves,
            "duties": duties,
        }

    @staticmethod
    def _fallback_status(
        *,
        employee_id: UUID,
        work_date: date,
        context: dict[str, object],
    ) -> str:
        duties = cast(dict[UUID, list[FieldDutyRequest]], context["duties"])
        leaves = cast(dict[UUID, list[LeaveRequest]], context["leaves"])
        holidays = cast(dict[date, Holiday], context["holidays"])
        weekends = cast(set[int], context["weekends"])
        if any(
            item.start_date <= work_date <= item.end_date
            for item in duties.get(employee_id, [])
        ):
            return "field_duty"
        for item in leaves.get(employee_id, []):
            if item.start_date <= work_date <= item.end_date:
                return "leave" if item.day_part == "full" else "partial"
        if work_date in holidays:
            return "holiday"
        if work_date.weekday() in weekends:
            return "weekly_off"
        return "uncalculated"

    @staticmethod
    def _row(
        employee: Employee,
        work_date: date,
        record: AttendanceRecord | None,
        detail: AttendanceRecordDetail | None,
        fallback_status: str,
    ) -> dict[str, object]:
        day_status = detail.day_status if detail else (
            record.status if record else fallback_status
        )
        return {
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "employee_name": employee.display_name,
            "work_date": work_date,
            "base_status": record.status if record else "uncalculated",
            "day_status": day_status,
            "check_in_at": record.check_in_at if record else None,
            "check_out_at": record.check_out_at if record else None,
            "worked_minutes": record.worked_minutes if record else 0,
            "late_minutes": record.late_minutes if record else 0,
            "planned_minutes": detail.planned_minutes if detail else 0,
            "early_arrival_minutes": detail.early_arrival_minutes if detail else 0,
            "early_departure_minutes": detail.early_departure_minutes if detail else 0,
            "late_departure_minutes": detail.late_departure_minutes if detail else 0,
            "regular_overtime_minutes": (
                detail.regular_overtime_minutes if detail else 0
            ),
            "holiday_overtime_minutes": (
                detail.holiday_overtime_minutes if detail else 0
            ),
            "source_event_count": record.source_punch_count if record else 0,
            "source_revision": record.source_revision if record else None,
            "engine_version": detail.engine_version if detail else (
                record.calculation_version if record else None
            ),
            "explanation_trace": detail.explanation_trace if detail else [],
        }

    def daily_rows(
        self,
        *,
        organization_id: UUID,
        work_date: date,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        self.company(organization_id)
        employees = self.employees(
            organization_id=organization_id,
            from_date=work_date,
            to_date=work_date,
            limit=limit,
            offset=offset,
        )
        employee_ids = [item.id for item in employees]
        records = self._records(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=work_date,
            to_date=work_date,
        )
        context = self._range_context(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=work_date,
            to_date=work_date,
        )
        return [
            self._row(
                employee,
                work_date,
                *(records.get((employee.id, work_date), (None, None))),
                self._fallback_status(
                    employee_id=employee.id,
                    work_date=work_date,
                    context=context,
                ),
            )
            for employee in employees
        ]

    def employee_detail(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict[str, object]:
        self.validate_range(from_date, to_date)
        employee = self.session.get(Employee, employee_id)
        if employee is None or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        records = self._records(
            organization_id=organization_id,
            employee_ids=[employee_id],
            from_date=from_date,
            to_date=to_date,
        )
        context = self._range_context(
            organization_id=organization_id,
            employee_ids=[employee_id],
            from_date=from_date,
            to_date=to_date,
        )
        rows: list[dict[str, object]] = []
        cursor = from_date
        while cursor <= to_date:
            record, detail = records.get((employee_id, cursor), (None, None))
            rows.append(
                self._row(
                    employee,
                    cursor,
                    record,
                    detail,
                    self._fallback_status(
                        employee_id=employee_id,
                        work_date=cursor,
                        context=context,
                    ),
                )
            )
            cursor += timedelta(days=1)
        status_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            status_counts[str(row["day_status"])] += 1
        return {
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "employee_name": employee.display_name,
            "from_date": from_date,
            "to_date": to_date,
            "status_counts": dict(status_counts),
            "worked_minutes": sum(int(row["worked_minutes"]) for row in rows),
            "late_minutes": sum(int(row["late_minutes"]) for row in rows),
            "regular_overtime_minutes": sum(
                int(row["regular_overtime_minutes"]) for row in rows
            ),
            "holiday_overtime_minutes": sum(
                int(row["holiday_overtime_minutes"]) for row in rows
            ),
            "records": rows,
        }

    def monthly_summary(
        self,
        *,
        organization_id: UUID,
        from_date: date,
        to_date: date,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        self.validate_range(from_date, to_date, max_days=MAX_MATRIX_DAYS)
        employees = self.employees(
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        employee_ids = [item.id for item in employees]
        records = self._records(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=from_date,
            to_date=to_date,
        )
        context = self._range_context(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=from_date,
            to_date=to_date,
        )
        summaries: list[dict[str, object]] = []
        for employee in employees:
            counts: dict[str, int] = defaultdict(int)
            worked = late = regular_ot = holiday_ot = 0
            cursor = from_date
            while cursor <= to_date:
                record, detail = records.get((employee.id, cursor), (None, None))
                row = self._row(
                    employee,
                    cursor,
                    record,
                    detail,
                    self._fallback_status(
                        employee_id=employee.id,
                        work_date=cursor,
                        context=context,
                    ),
                )
                counts[str(row["day_status"])] += 1
                worked += int(row["worked_minutes"])
                late += int(row["late_minutes"])
                regular_ot += int(row["regular_overtime_minutes"])
                holiday_ot += int(row["holiday_overtime_minutes"])
                cursor += timedelta(days=1)
            summaries.append(
                {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "employee_name": employee.display_name,
                    "status_counts": dict(counts),
                    "worked_minutes": worked,
                    "late_minutes": late,
                    "regular_overtime_minutes": regular_ot,
                    "holiday_overtime_minutes": holiday_ot,
                }
            )
        return summaries

    def department_coverage(
        self,
        *,
        organization_id: UUID,
        work_date: date,
    ) -> list[dict[str, object]]:
        employees = self.all_employees_bounded(
            organization_id=organization_id,
            observed_on=work_date,
        )
        employee_ids = [item.id for item in employees]
        records = self._records(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=work_date,
            to_date=work_date,
        )
        context = self._range_context(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=work_date,
            to_date=work_date,
        )
        nodes = {
            item.id: item
            for item in self.session.scalars(
                select(OrganizationNode).where(
                    OrganizationNode.organization_id == organization_id
                )
            ).all()
        }
        assignments = self.session.scalars(
            select(EmployeeOrganizationAssignment)
            .where(
                EmployeeOrganizationAssignment.organization_id == organization_id,
                EmployeeOrganizationAssignment.employee_id.in_(employee_ids),
                EmployeeOrganizationAssignment.is_primary.is_(True),
                EmployeeOrganizationAssignment.starts_on <= work_date,
                or_(
                    EmployeeOrganizationAssignment.ends_on.is_(None),
                    EmployeeOrganizationAssignment.ends_on >= work_date,
                ),
            )
            .order_by(
                EmployeeOrganizationAssignment.employee_id,
                EmployeeOrganizationAssignment.starts_on.desc(),
            )
        ).all()
        assignment_by_employee: dict[UUID, EmployeeOrganizationAssignment] = {}
        for item in assignments:
            assignment_by_employee.setdefault(item.employee_id, item)

        def department_for(employee_id: UUID) -> OrganizationNode | None:
            assignment = assignment_by_employee.get(employee_id)
            node = nodes.get(assignment.organization_node_id) if assignment else None
            visited: set[UUID] = set()
            while node is not None and node.id not in visited:
                visited.add(node.id)
                if node.node_type == "department":
                    return node
                node = nodes.get(node.parent_id) if node.parent_id else None
            return None

        grouped: dict[tuple[UUID | None, str], dict[str, object]] = {}
        for employee in employees:
            department = department_for(employee.id)
            key = (
                department.id if department else None,
                department.name if department else "Unassigned",
            )
            bucket = grouped.setdefault(
                key,
                {
                    "employee_count": 0,
                    "statuses": defaultdict(int),
                    "employee_ids": [],
                },
            )
            bucket["employee_count"] = int(bucket["employee_count"]) + 1
            employee_list = cast(list[UUID], bucket["employee_ids"])
            employee_list.append(employee.id)
            record, detail = records.get((employee.id, work_date), (None, None))
            day_status = (
                detail.day_status
                if detail
                else record.status
                if record
                else self._fallback_status(
                    employee_id=employee.id,
                    work_date=work_date,
                    context=context,
                )
            )
            statuses = cast(defaultdict[str, int], bucket["statuses"])
            statuses[day_status] += 1

        output: list[dict[str, object]] = []
        for (department_id, department_name), bucket in sorted(
            grouped.items(), key=lambda item: item[0][1].casefold()
        ):
            total = int(bucket["employee_count"])
            statuses = cast(defaultdict[str, int], bucket["statuses"])
            attended = int(statuses["present"]) + int(statuses["partial"])
            output.append(
                {
                    "department_id": department_id,
                    "department_name": department_name,
                    "employee_count": total,
                    "coverage_count": attended,
                    "coverage_percent": (
                        round((attended / total) * 100, 2) if total else 0.0
                    ),
                    "status_counts": dict(statuses),
                    "employee_ids": bucket["employee_ids"],
                }
            )
        return output

    def hajiri_register(
        self,
        *,
        organization_id: UUID,
        bs_year: int,
        bs_month: int,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, object]:
        metadata = BsDateService.month_metadata(bs_year, bs_month)
        employees = self.employees(
            organization_id=organization_id,
            from_date=metadata.first_ad_date,
            to_date=metadata.last_ad_date,
            limit=limit,
            offset=offset,
        )
        employee_ids = [item.id for item in employees]
        records = self._records(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=metadata.first_ad_date,
            to_date=metadata.last_ad_date,
        )
        context = self._range_context(
            organization_id=organization_id,
            employee_ids=employee_ids,
            from_date=metadata.first_ad_date,
            to_date=metadata.last_ad_date,
        )
        rows: list[dict[str, object]] = []
        for employee in employees:
            days: dict[str, str] = {}
            counts: dict[str, int] = defaultdict(int)
            for day in range(1, metadata.days + 1):
                ad_date = BsDateService.bs_to_ad(f"{bs_year:04d}-{bs_month:02d}-{day:02d}")
                record, detail = records.get((employee.id, ad_date), (None, None))
                status = (
                    detail.day_status
                    if detail
                    else record.status
                    if record
                    else self._fallback_status(
                        employee_id=employee.id,
                        work_date=ad_date,
                        context=context,
                    )
                )
                days[str(day)] = STATUS_CODES[status]
                counts[status] += 1
            rows.append(
                {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "employee_name": employee.display_name,
                    "days": days,
                    "status_counts": dict(counts),
                }
            )
        return {
            "bs_year": bs_year,
            "bs_month": bs_month,
            "month_name": metadata.month_name,
            "days_in_month": metadata.days,
            "first_ad_date": metadata.first_ad_date,
            "last_ad_date": metadata.last_ad_date,
            "rows": rows,
        }

    def attendance_events(
        self,
        *,
        organization_id: UUID,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        employee_id: UUID | None = None,
        device_id: UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        if limit < 1 or limit > 1000:
            raise ValueError("event page size must be between 1 and 1000")
        if offset < 0:
            raise ValueError("event offset cannot be negative")
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
            query = query.where(RawPunch.occurred_at >= _as_utc(from_at))
        if to_at is not None:
            query = query.where(RawPunch.occurred_at <= _as_utc(to_at))
        if employee_id is not None:
            query = query.where(DeviceEmployeeMapping.employee_id == employee_id)
        if device_id is not None:
            query = query.where(RawPunch.device_id == device_id)
        rows = self.session.execute(
            query.order_by(RawPunch.occurred_at.desc(), RawPunch.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [
            {
                "id": punch.id,
                "employee_id": mapped_employee_id,
                "source": "device",
                "device_id": punch.device_id,
                "occurred_at": _as_utc(punch.occurred_at),
                "event_type": punch.punch_kind,
                "verification_method": punch.verification_method,
                "source_fingerprint": punch.source_fingerprint,
                "manual_status": None,
            }
            for punch, mapped_employee_id in rows
        ]

    def employee_day_events(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        work_date: date,
    ) -> list[dict[str, object]]:
        company = self.company(organization_id)
        employee = self.session.get(Employee, employee_id)
        if employee is None or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        timezone = ZoneInfo(company.timezone)
        start_local = datetime.combine(work_date, time.min, tzinfo=timezone)
        end_local = start_local + timedelta(days=2)
        raw_events = self.attendance_events(
            organization_id=organization_id,
            from_at=start_local.astimezone(UTC),
            to_at=end_local.astimezone(UTC),
            employee_id=employee_id,
            limit=1000,
        )
        manual_items = self.session.scalars(
            select(ManualAttendanceEvent)
            .where(
                ManualAttendanceEvent.organization_id == organization_id,
                ManualAttendanceEvent.employee_id == employee_id,
                ManualAttendanceEvent.event_time >= start_local.astimezone(UTC),
                ManualAttendanceEvent.event_time < end_local.astimezone(UTC),
            )
            .order_by(ManualAttendanceEvent.event_time, ManualAttendanceEvent.id)
            .limit(1000)
        ).all()
        events = list(raw_events)
        events.extend(
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "source": "manual",
                "device_id": None,
                "occurred_at": _as_utc(item.event_time),
                "event_type": item.event_type,
                "verification_method": None,
                "source_fingerprint": None,
                "manual_status": item.status,
            }
            for item in manual_items
        )
        events.sort(key=lambda item: (item["occurred_at"], str(item["id"])))
        return events
