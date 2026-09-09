import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance import AttendanceHistory, AttendanceRecord
from hajiriflow.db.models.attendance_baseline import (
    AttendancePeriodLock,
    AttendancePolicy,
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
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import (
    CompanyProfile,
    Employee,
    EmployeeOrganizationAssignment,
    Shift,
    ShiftAssignment,
)
from hajiriflow.identity.audit import redact_audit_payload

ENGINE_VERSION = "attendance-v2"
DEFAULT_WEEKENDS = [5]


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    occurred_at: datetime
    event_type: str
    source: str
    source_id: UUID


def _minutes(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() // 60))


def _aware(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value


class AttendanceEngineService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _company(self, organization_id: UUID) -> CompanyProfile:
        company = self.session.get(CompanyProfile, organization_id)
        if not company:
            raise LookupError("organization not found")
        return company

    def _employee(self, organization_id: UUID, employee_id: UUID) -> Employee:
        employee = self.session.get(Employee, employee_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        return employee

    def policy(self, organization_id: UUID) -> AttendancePolicy:
        self._company(organization_id)
        item = self.session.get(AttendancePolicy, organization_id)
        if item is None:
            item = AttendancePolicy(organization_id=organization_id)
            self.session.add(item)
            self.session.flush()
        return item

    def is_locked(self, organization_id: UUID, work_date: date) -> AttendancePeriodLock | None:
        return self.session.scalar(
            select(AttendancePeriodLock).where(
                AttendancePeriodLock.organization_id == organization_id,
                AttendancePeriodLock.status == "locked",
                AttendancePeriodLock.starts_on <= work_date,
                AttendancePeriodLock.ends_on >= work_date,
            )
        )

    def _resolve_shift(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        work_date: date,
    ) -> Shift | None:
        employee_assignment = self.session.scalar(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.organization_id == organization_id,
                ShiftAssignment.employee_id == employee_id,
                ShiftAssignment.starts_on <= work_date,
                or_(
                    ShiftAssignment.ends_on.is_(None),
                    ShiftAssignment.ends_on >= work_date,
                ),
            )
            .order_by(ShiftAssignment.starts_on.desc(), ShiftAssignment.id.desc())
            .limit(1)
        )
        if employee_assignment:
            return self.session.get(Shift, employee_assignment.shift_id)

        organization_assignment = self.session.scalar(
            select(EmployeeOrganizationAssignment)
            .where(
                EmployeeOrganizationAssignment.organization_id == organization_id,
                EmployeeOrganizationAssignment.employee_id == employee_id,
                EmployeeOrganizationAssignment.starts_on <= work_date,
                or_(
                    EmployeeOrganizationAssignment.ends_on.is_(None),
                    EmployeeOrganizationAssignment.ends_on >= work_date,
                ),
                EmployeeOrganizationAssignment.is_primary.is_(True),
            )
            .order_by(
                EmployeeOrganizationAssignment.starts_on.desc(),
                EmployeeOrganizationAssignment.id.desc(),
            )
            .limit(1)
        )
        if not organization_assignment:
            return None
        organization_shift = self.session.scalar(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.organization_id == organization_id,
                ShiftAssignment.organization_node_id
                == organization_assignment.organization_node_id,
                ShiftAssignment.starts_on <= work_date,
                or_(
                    ShiftAssignment.ends_on.is_(None),
                    ShiftAssignment.ends_on >= work_date,
                ),
            )
            .order_by(ShiftAssignment.starts_on.desc(), ShiftAssignment.id.desc())
            .limit(1)
        )
        return self.session.get(Shift, organization_shift.shift_id) if organization_shift else None

    @staticmethod
    def _schedule(
        *,
        shift: Shift | None,
        work_date: date,
        timezone: ZoneInfo,
        policy: AttendancePolicy,
    ) -> tuple[datetime, datetime, datetime, datetime, int]:
        if shift is None:
            local_start = datetime.combine(work_date, time.min, tzinfo=timezone)
            local_end = local_start + timedelta(days=1)
            return local_start, local_end, local_start, local_end, 0
        scheduled_start = datetime.combine(work_date, shift.starts_at, tzinfo=timezone)
        scheduled_end = datetime.combine(work_date, shift.ends_at, tzinfo=timezone)
        if shift.ends_at <= shift.starts_at:
            scheduled_end += timedelta(days=1)
        window_start = scheduled_start - timedelta(minutes=policy.pre_shift_window_minutes)
        window_end = scheduled_end + timedelta(minutes=policy.post_shift_window_minutes)
        planned = max(
            0,
            _minutes(scheduled_end - scheduled_start) - shift.break_minutes,
        )
        return scheduled_start, scheduled_end, window_start, window_end, planned

    def _raw_events(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[TimelineEvent]:
        query = (
            select(RawPunch)
            .join(
                DeviceUser,
                (DeviceUser.device_id == RawPunch.device_id)
                & (DeviceUser.external_user_id == RawPunch.device_user_identifier),
            )
            .join(
                DeviceEmployeeMapping,
                DeviceEmployeeMapping.device_user_id == DeviceUser.id,
            )
            .where(
                RawPunch.organization_id == organization_id,
                DeviceEmployeeMapping.employee_id == employee_id,
                DeviceEmployeeMapping.status == "active",
                RawPunch.occurred_at >= start_at.astimezone(UTC),
                RawPunch.occurred_at < end_at.astimezone(UTC),
                RawPunch.punch_kind.in_(("in", "out")),
            )
            .order_by(RawPunch.occurred_at, RawPunch.id)
        )
        return [
            TimelineEvent(
                occurred_at=item.occurred_at,
                event_type=item.punch_kind,
                source="device",
                source_id=item.id,
            )
            for item in self.session.scalars(query).all()
        ]

    def _manual_events(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[TimelineEvent]:
        query = (
            select(ManualAttendanceEvent)
            .where(
                ManualAttendanceEvent.organization_id == organization_id,
                ManualAttendanceEvent.employee_id == employee_id,
                ManualAttendanceEvent.status == "approved",
                ManualAttendanceEvent.event_time >= start_at.astimezone(UTC),
                ManualAttendanceEvent.event_time < end_at.astimezone(UTC),
            )
            .order_by(ManualAttendanceEvent.event_time, ManualAttendanceEvent.id)
        )
        return [
            TimelineEvent(
                occurred_at=item.event_time,
                event_type=item.event_type,
                source="manual",
                source_id=item.id,
            )
            for item in self.session.scalars(query).all()
        ]

    @staticmethod
    def _deduplicate(
        events: list[TimelineEvent],
        *,
        window_seconds: int,
    ) -> tuple[list[TimelineEvent], int]:
        ordered = sorted(
            events,
            key=lambda item: (
                item.occurred_at,
                0 if item.source == "device" else 1,
                str(item.source_id),
            ),
        )
        if window_seconds <= 0:
            return ordered, 0
        kept: list[TimelineEvent] = []
        duplicates = 0
        last_by_type: dict[str, TimelineEvent] = {}
        for item in ordered:
            previous = last_by_type.get(item.event_type)
            if previous is not None:
                delta = item.occurred_at - previous.occurred_at
                if timedelta(0) <= delta <= timedelta(seconds=window_seconds):
                    duplicates += 1
                    continue
            kept.append(item)
            last_by_type[item.event_type] = item
        return kept, duplicates

    def _day_context(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        work_date: date,
    ) -> dict:
        settings = self.session.get(OrganizationCalendarSettings, organization_id)
        weekends = settings.weekend_weekdays if settings else DEFAULT_WEEKENDS
        weekend = work_date.weekday() in set(weekends)
        holiday = self.session.scalar(
            select(Holiday).where(
                Holiday.organization_id == organization_id,
                Holiday.holiday_date == work_date,
                Holiday.status == "active",
                Holiday.category != "optional",
            )
        )
        field_duty = self.session.scalar(
            select(FieldDutyRequest).where(
                FieldDutyRequest.organization_id == organization_id,
                FieldDutyRequest.employee_id == employee_id,
                FieldDutyRequest.status == "approved",
                FieldDutyRequest.start_date <= work_date,
                FieldDutyRequest.end_date >= work_date,
            )
        )
        leave = self.session.scalar(
            select(LeaveRequest).where(
                LeaveRequest.organization_id == organization_id,
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= work_date,
                LeaveRequest.end_date >= work_date,
            )
        )
        return {
            "weekend": weekend,
            "holiday": holiday,
            "field_duty": field_duty,
            "leave": leave,
        }

    @staticmethod
    def _base_status(
        check_in_at: datetime | None,
        check_out_at: datetime | None,
    ) -> str:
        if check_in_at is not None and check_out_at is not None:
            return "present"
        if check_in_at is not None or check_out_at is not None:
            return "partial"
        return "absent"

    @staticmethod
    def _day_status(base_status: str, context: dict) -> str:
        field_duty = context["field_duty"]
        leave = context["leave"]
        if field_duty is not None:
            return "field_duty"
        if leave is not None and leave.day_part == "full":
            return "leave"
        if context["holiday"] is not None:
            return "holiday"
        if context["weekend"]:
            return "weekly_off"
        if leave is not None and leave.day_part != "full" and base_status == "absent":
            return "partial"
        return base_status

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _trace(
        *,
        shift: Shift | None,
        context: dict,
        events: list[TimelineEvent],
        duplicate_count: int,
        check_in_at: datetime | None,
        check_out_at: datetime | None,
        base_status: str,
        day_status: str,
    ) -> list[dict]:
        trace: list[dict] = [
            {
                "rule": "shift_resolution",
                "decision": "shift" if shift else "no_shift",
                "reference_id": str(shift.id) if shift else None,
            },
            {
                "rule": "event_timeline",
                "decision": "normalized",
                "event_count": len(events),
                "duplicate_count": duplicate_count,
            },
            {
                "rule": "first_in_last_out",
                "decision": base_status,
                "check_in_at": check_in_at.isoformat() if check_in_at else None,
                "check_out_at": check_out_at.isoformat() if check_out_at else None,
            },
        ]
        if context["field_duty"] is not None:
            trace.append(
                {
                    "rule": "field_duty",
                    "decision": "approved",
                    "reference_id": str(context["field_duty"].id),
                }
            )
        if context["leave"] is not None:
            trace.append(
                {
                    "rule": "leave",
                    "decision": context["leave"].day_part,
                    "reference_id": str(context["leave"].id),
                }
            )
        if context["holiday"] is not None:
            trace.append(
                {
                    "rule": "holiday",
                    "decision": "non_working",
                    "reference_id": str(context["holiday"].id),
                }
            )
        if context["weekend"]:
            trace.append({"rule": "weekly_off", "decision": "non_working"})
        trace.append({"rule": "status_priority", "decision": day_status})
        return trace

    def calculate_day(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        work_date: date,
        actor_user_id: UUID | None = None,
    ) -> AttendanceRecord:
        company = self._company(organization_id)
        self._employee(organization_id, employee_id)
        period_lock = self.is_locked(organization_id, work_date)
        if period_lock is not None:
            raise ValueError("attendance period is locked; reopen it before recalculation")

        timezone = ZoneInfo(company.timezone)
        policy = self.policy(organization_id)
        shift = self._resolve_shift(
            organization_id=organization_id,
            employee_id=employee_id,
            work_date=work_date,
        )
        scheduled_start, scheduled_end, window_start, window_end, planned_minutes = (
            self._schedule(
                shift=shift,
                work_date=work_date,
                timezone=timezone,
                policy=policy,
            )
        )
        all_events = self._raw_events(
            organization_id=organization_id,
            employee_id=employee_id,
            start_at=window_start,
            end_at=window_end,
        )
        all_events.extend(
            self._manual_events(
                organization_id=organization_id,
                employee_id=employee_id,
                start_at=window_start,
                end_at=window_end,
            )
        )
        events, duplicate_count = self._deduplicate(
            all_events,
            window_seconds=policy.duplicate_window_seconds,
        )
        in_events = [item for item in events if item.event_type == "in"]
        out_events = [item for item in events if item.event_type == "out"]
        check_in_at = in_events[0].occurred_at if in_events else None
        check_out_at = out_events[-1].occurred_at if out_events else None
        invalid_order = (
            check_in_at is not None
            and check_out_at is not None
            and check_out_at < check_in_at
        )
        if invalid_order:
            check_out_at = None

        break_minutes = shift.break_minutes if shift else 0
        worked_minutes = 0
        if check_in_at is not None and check_out_at is not None:
            worked_minutes = max(
                0,
                _minutes(check_out_at - check_in_at) - break_minutes,
            )

        grace_minutes = shift.grace_minutes if shift else 0
        late_minutes = 0
        early_arrival_minutes = 0
        early_departure_minutes = 0
        late_departure_minutes = 0
        if shift and check_in_at is not None:
            local_in = _aware(check_in_at, timezone).astimezone(timezone)
            late_minutes = _minutes(
                local_in - (scheduled_start + timedelta(minutes=grace_minutes))
            )
            early_arrival_minutes = _minutes(scheduled_start - local_in)
        if shift and check_out_at is not None:
            local_out = _aware(check_out_at, timezone).astimezone(timezone)
            early_departure_minutes = _minutes(
                (scheduled_end - timedelta(minutes=grace_minutes)) - local_out
            )
            late_departure_minutes = _minutes(local_out - scheduled_end)

        context = self._day_context(
            organization_id=organization_id,
            employee_id=employee_id,
            work_date=work_date,
        )
        base_status = self._base_status(check_in_at, check_out_at)
        day_status = self._day_status(base_status, context)
        non_working = context["holiday"] is not None or context["weekend"]
        regular_overtime_minutes = (
            max(0, worked_minutes - planned_minutes)
            if not non_working and day_status not in {"leave", "field_duty"}
            else 0
        )
        holiday_overtime_minutes = worked_minutes if non_working else 0

        trace = self._trace(
            shift=shift,
            context=context,
            events=events,
            duplicate_count=duplicate_count,
            check_in_at=check_in_at,
            check_out_at=check_out_at,
            base_status=base_status,
            day_status=day_status,
        )
        if invalid_order:
            trace.append(
                {
                    "rule": "event_order",
                    "decision": "out_before_in_ignored",
                }
            )

        fingerprint_payload = {
            "engine_version": ENGINE_VERSION,
            "organization_id": str(organization_id),
            "employee_id": str(employee_id),
            "work_date": work_date.isoformat(),
            "shift": (
                {
                    "id": str(shift.id),
                    "starts_at": shift.starts_at.isoformat(),
                    "ends_at": shift.ends_at.isoformat(),
                    "break_minutes": shift.break_minutes,
                    "grace_minutes": shift.grace_minutes,
                }
                if shift
                else None
            ),
            "policy": {
                "duplicate_window_seconds": policy.duplicate_window_seconds,
                "pre_shift_window_minutes": policy.pre_shift_window_minutes,
                "post_shift_window_minutes": policy.post_shift_window_minutes,
            },
            "events": [
                {
                    "id": str(item.source_id),
                    "source": item.source,
                    "type": item.event_type,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in events
            ],
            "context": {
                "weekend": context["weekend"],
                "holiday_id": (
                    str(context["holiday"].id) if context["holiday"] else None
                ),
                "leave_id": str(context["leave"].id) if context["leave"] else None,
                "field_duty_id": (
                    str(context["field_duty"].id) if context["field_duty"] else None
                ),
            },
        }
        input_fingerprint = self._fingerprint(fingerprint_payload)
        record = self.session.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.work_date == work_date,
            )
        )
        existing_detail = (
            self.session.get(AttendanceRecordDetail, record.id) if record else None
        )
        if (
            record is not None
            and existing_detail is not None
            and existing_detail.input_fingerprint == input_fingerprint
            and existing_detail.engine_version == ENGINE_VERSION
        ):
            return record

        event_type = "recalculated" if record else "calculated"
        if record is None:
            record = AttendanceRecord(
                organization_id=organization_id,
                employee_id=employee_id,
                work_date=work_date,
                status=base_status,
                calculation_version=ENGINE_VERSION,
            )
            self.session.add(record)
            self.session.flush()
        else:
            record.source_revision += 1
        record.shift_id = shift.id if shift else None
        record.check_in_at = check_in_at
        record.check_out_at = check_out_at
        record.worked_minutes = worked_minutes
        record.late_minutes = late_minutes
        record.status = base_status
        record.calculation_version = ENGINE_VERSION
        record.source_punch_count = len(all_events)
        record.calculated_at = datetime.now(UTC)

        detail = existing_detail
        if detail is None:
            detail = AttendanceRecordDetail(attendance_record_id=record.id)
            self.session.add(detail)
        detail.day_status = day_status
        detail.planned_minutes = planned_minutes
        detail.break_minutes = break_minutes
        detail.early_arrival_minutes = early_arrival_minutes
        detail.early_departure_minutes = early_departure_minutes
        detail.late_departure_minutes = late_departure_minutes
        detail.regular_overtime_minutes = regular_overtime_minutes
        detail.holiday_overtime_minutes = holiday_overtime_minutes
        detail.duplicate_event_count = duplicate_count
        detail.input_fingerprint = input_fingerprint
        detail.engine_version = ENGINE_VERSION
        detail.explanation_trace = trace
        detail.updated_at = datetime.now(UTC)

        snapshot = {
            "record": {
                "id": str(record.id),
                "employee_id": str(record.employee_id),
                "work_date": record.work_date.isoformat(),
                "shift_id": str(record.shift_id) if record.shift_id else None,
                "check_in_at": (
                    record.check_in_at.isoformat() if record.check_in_at else None
                ),
                "check_out_at": (
                    record.check_out_at.isoformat() if record.check_out_at else None
                ),
                "worked_minutes": record.worked_minutes,
                "late_minutes": record.late_minutes,
                "status": record.status,
                "source_punch_count": record.source_punch_count,
                "source_revision": record.source_revision,
            },
            "detail": {
                "day_status": day_status,
                "planned_minutes": planned_minutes,
                "break_minutes": break_minutes,
                "early_arrival_minutes": early_arrival_minutes,
                "early_departure_minutes": early_departure_minutes,
                "late_departure_minutes": late_departure_minutes,
                "regular_overtime_minutes": regular_overtime_minutes,
                "holiday_overtime_minutes": holiday_overtime_minutes,
                "duplicate_event_count": duplicate_count,
                "input_fingerprint": input_fingerprint,
                "engine_version": ENGINE_VERSION,
                "explanation_trace": trace,
            },
        }
        self.session.add(
            AttendanceHistory(
                organization_id=organization_id,
                attendance_record_id=record.id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                snapshot=snapshot,
            )
        )
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=f"attendance.{event_type}",
                object_type="attendance_record",
                object_id=str(record.id),
                after_data=redact_audit_payload(
                    {
                        "employee_id": str(employee_id),
                        "work_date": work_date.isoformat(),
                        "day_status": day_status,
                        "source_revision": record.source_revision,
                        "engine_version": ENGINE_VERSION,
                        "input_fingerprint": input_fingerprint,
                    }
                ),
                context_data={"organization_id": str(organization_id)},
            )
        )
        self.session.flush()
        return record
