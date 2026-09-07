from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance import (
    AttendanceCorrection,
    AttendanceHistory,
    AttendanceRecord,
)
from hajiriflow.db.models.device import (
    DeviceEmployeeMapping,
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import CompanyProfile, Employee, Shift
from hajiriflow.identity.audit import redact_audit_payload
from hajiriflow.workforce.service import WorkforceService

CALCULATION_VERSION = "attendance-v1"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _snapshot(record: AttendanceRecord) -> dict[str, object]:
    return {
        "employee_id": str(record.employee_id),
        "work_date": record.work_date.isoformat(),
        "shift_id": str(record.shift_id) if record.shift_id else None,
        "check_in_at": (
            _as_utc(record.check_in_at).isoformat() if record.check_in_at else None
        ),
        "check_out_at": (
            _as_utc(record.check_out_at).isoformat() if record.check_out_at else None
        ),
        "worked_minutes": record.worked_minutes,
        "late_minutes": record.late_minutes,
        "status": record.status,
        "calculation_version": record.calculation_version,
        "source_punch_count": record.source_punch_count,
        "source_revision": record.source_revision,
    }


class AttendanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _organization(self, organization_id: UUID) -> CompanyProfile:
        organization = self.session.get(CompanyProfile, organization_id)
        if not organization:
            raise LookupError("organization not found")
        return organization

    def _employee(self, organization_id: UUID, employee_id: UUID) -> Employee:
        employee = self.session.get(Employee, employee_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        return employee

    def _history(
        self,
        *,
        record: AttendanceRecord,
        event_type: str,
        actor_user_id: UUID | None,
        correction_id: UUID | None = None,
        reason: str | None = None,
        snapshot: dict | None = None,
    ) -> AttendanceHistory:
        history = AttendanceHistory(
            organization_id=record.organization_id,
            attendance_record_id=record.id,
            correction_id=correction_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            reason=reason,
            snapshot=redact_audit_payload(snapshot or _snapshot(record)),
        )
        self.session.add(history)
        return history

    def _audit(
        self,
        *,
        record: AttendanceRecord,
        actor_user_id: UUID | None,
        action: str,
        reason: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                object_type="attendance_record",
                object_id=str(record.id),
                reason=reason,
                before_data=redact_audit_payload(before) if before else None,
                after_data=redact_audit_payload(after) if after else None,
                context_data={"organization_id": str(record.organization_id)},
            )
        )

    def _day_bounds(
        self, organization: CompanyProfile, work_date: date
    ) -> tuple[datetime, datetime]:
        timezone = ZoneInfo(organization.timezone)
        start_local = datetime.combine(work_date, datetime.min.time(), tzinfo=timezone)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    def _mapped_punches(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[RawPunch]:
        query = (
            select(RawPunch)
            .join(
                DeviceUser,
                and_(
                    DeviceUser.device_id == RawPunch.device_id,
                    DeviceUser.external_user_id == RawPunch.device_user_identifier,
                ),
            )
            .join(
                DeviceEmployeeMapping,
                DeviceEmployeeMapping.device_user_id == DeviceUser.id,
            )
            .where(
                RawPunch.organization_id == organization_id,
                DeviceUser.active.is_(True),
                DeviceEmployeeMapping.employee_id == employee_id,
                DeviceEmployeeMapping.status == "active",
                RawPunch.occurred_at >= starts_at,
                RawPunch.occurred_at < ends_at,
            )
            .order_by(RawPunch.occurred_at, RawPunch.id)
        )
        return list(self.session.scalars(query).all())

    @staticmethod
    def _status(check_in_at: datetime | None, check_out_at: datetime | None) -> str:
        if check_in_at and check_out_at and _as_utc(check_out_at) >= _as_utc(check_in_at):
            return "present"
        if check_in_at or check_out_at:
            return "partial"
        return "absent"

    @staticmethod
    def _metrics(
        *,
        work_date: date,
        check_in_at: datetime | None,
        check_out_at: datetime | None,
        shift: Shift | None,
        organization_timezone: str,
    ) -> tuple[int, int]:
        worked_minutes = 0
        late_minutes = 0
        check_in_utc = _as_utc(check_in_at)
        check_out_utc = _as_utc(check_out_at)
        if check_in_utc and check_out_utc and check_out_utc >= check_in_utc:
            worked_minutes = int((check_out_utc - check_in_utc).total_seconds() // 60)
            if shift:
                worked_minutes = max(0, worked_minutes - shift.break_minutes)
        if shift and check_in_utc:
            timezone = ZoneInfo(organization_timezone)
            scheduled = datetime.combine(work_date, shift.starts_at, tzinfo=timezone)
            allowed = scheduled + timedelta(minutes=shift.grace_minutes)
            local_check_in = check_in_utc.astimezone(timezone)
            late_minutes = max(0, int((local_check_in - allowed).total_seconds() // 60))
        return worked_minutes, late_minutes

    def calculate_day(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        work_date: date,
        actor_user_id: UUID | None = None,
        calculation_version: str = CALCULATION_VERSION,
    ) -> AttendanceRecord:
        organization = self._organization(organization_id)
        self._employee(organization_id, employee_id)
        _org_assignment, _shift_assignment, shift = WorkforceService(
            self.session
        ).resolve_employee_context(
            organization_id=organization_id,
            employee_id=employee_id,
            on_date=work_date,
        )
        starts_at, ends_at = self._day_bounds(organization, work_date)
        punches = self._mapped_punches(
            organization_id=organization_id,
            employee_id=employee_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        in_punches = [punch for punch in punches if punch.punch_kind == "in"]
        out_punches = [punch for punch in punches if punch.punch_kind == "out"]
        check_in_at = in_punches[0].occurred_at if in_punches else None
        check_out_at = out_punches[-1].occurred_at if out_punches else None
        status = self._status(check_in_at, check_out_at)
        worked_minutes, late_minutes = self._metrics(
            work_date=work_date,
            check_in_at=check_in_at,
            check_out_at=check_out_at,
            shift=shift,
            organization_timezone=organization.timezone,
        )

        record = self.session.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == organization_id,
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.work_date == work_date,
            )
        )
        before = _snapshot(record) if record else None
        event_type = "recalculated" if record else "calculated"
        if record is None:
            record = AttendanceRecord(
                organization_id=organization_id,
                employee_id=employee_id,
                work_date=work_date,
                status=status,
                calculation_version=calculation_version,
            )
            self.session.add(record)
        else:
            record.source_revision += 1
        record.shift_id = shift.id if shift else None
        record.check_in_at = check_in_at
        record.check_out_at = check_out_at
        record.worked_minutes = worked_minutes
        record.late_minutes = late_minutes
        record.status = status
        record.calculation_version = calculation_version
        record.source_punch_count = len(punches)
        record.calculated_at = utc_now()
        record.updated_at = utc_now()
        self.session.flush()
        after = _snapshot(record)
        self._history(
            record=record,
            event_type=event_type,
            actor_user_id=actor_user_id,
        )
        self._audit(
            record=record,
            actor_user_id=actor_user_id,
            action=f"attendance.{event_type}",
            before=before,
            after=after,
        )
        return record

    def request_correction(
        self,
        *,
        organization_id: UUID,
        attendance_record_id: UUID,
        requested_by: UUID,
        reason: str,
        proposed_check_in_at: datetime | None = None,
        proposed_check_out_at: datetime | None = None,
        proposed_status: str | None = None,
    ) -> AttendanceCorrection:
        record = self.session.get(AttendanceRecord, attendance_record_id)
        if not record or record.organization_id != organization_id:
            raise LookupError("attendance record not found")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 10:
            raise ValueError("correction reason must be at least 10 characters")
        for value in (proposed_check_in_at, proposed_check_out_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("correction timestamps must include a timezone")
        if proposed_status not in {None, "present", "absent", "partial"}:
            raise ValueError("unsupported attendance status")
        pending = self.session.scalar(
            select(AttendanceCorrection.id).where(
                AttendanceCorrection.attendance_record_id == record.id,
                AttendanceCorrection.status == "pending",
            )
        )
        if pending:
            raise ValueError("attendance record already has a pending correction")
        correction = AttendanceCorrection(
            organization_id=organization_id,
            attendance_record_id=record.id,
            requested_by=requested_by,
            reason=normalized_reason,
            proposed_check_in_at=proposed_check_in_at,
            proposed_check_out_at=proposed_check_out_at,
            proposed_status=proposed_status,
        )
        self.session.add(correction)
        self.session.flush()
        proposal = {
            "record": _snapshot(record),
            "proposal": {
                "check_in_at": (
                    _as_utc(proposed_check_in_at).isoformat()
                    if proposed_check_in_at
                    else None
                ),
                "check_out_at": (
                    _as_utc(proposed_check_out_at).isoformat()
                    if proposed_check_out_at
                    else None
                ),
                "status": proposed_status,
            },
        }
        self._history(
            record=record,
            correction_id=correction.id,
            event_type="correction_requested",
            actor_user_id=requested_by,
            reason=normalized_reason,
            snapshot=proposal,
        )
        self._audit(
            record=record,
            actor_user_id=requested_by,
            action="attendance.correction.requested",
            reason=normalized_reason,
            after=proposal,
        )
        return correction

    def decide_correction(
        self,
        *,
        organization_id: UUID,
        correction_id: UUID,
        decided_by: UUID,
        approve: bool,
        decision_reason: str,
    ) -> AttendanceCorrection:
        correction = self.session.get(AttendanceCorrection, correction_id)
        if not correction or correction.organization_id != organization_id:
            raise LookupError("attendance correction not found")
        if correction.status != "pending":
            raise ValueError("attendance correction has already been decided")
        if correction.requested_by == decided_by:
            raise ValueError("attendance corrections require independent approval")
        normalized_reason = decision_reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("decision reason must be at least 5 characters")
        record = self.session.get(AttendanceRecord, correction.attendance_record_id)
        if not record or record.organization_id != organization_id:
            raise LookupError("attendance record not found")
        before = _snapshot(record)
        correction.decided_by = decided_by
        correction.decided_at = utc_now()
        correction.decision_reason = normalized_reason
        correction.status = "approved" if approve else "rejected"

        if approve:
            if correction.proposed_status == "absent":
                record.check_in_at = None
                record.check_out_at = None
            else:
                if correction.proposed_check_in_at is not None:
                    record.check_in_at = correction.proposed_check_in_at
                if correction.proposed_check_out_at is not None:
                    record.check_out_at = correction.proposed_check_out_at
            record.status = correction.proposed_status or self._status(
                record.check_in_at, record.check_out_at
            )
            organization = self._organization(organization_id)
            shift = self.session.get(Shift, record.shift_id) if record.shift_id else None
            record.worked_minutes, record.late_minutes = self._metrics(
                work_date=record.work_date,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
                shift=shift,
                organization_timezone=organization.timezone,
            )
            record.source_revision += 1
            record.updated_at = utc_now()

        self.session.flush()
        after = _snapshot(record)
        event_type = "correction_approved" if approve else "correction_rejected"
        self._history(
            record=record,
            correction_id=correction.id,
            event_type=event_type,
            actor_user_id=decided_by,
            reason=normalized_reason,
        )
        self._audit(
            record=record,
            actor_user_id=decided_by,
            action=f"attendance.{event_type}",
            reason=normalized_reason,
            before=before,
            after=after,
        )
        return correction
