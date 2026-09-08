from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from hajiriflow.calendar_leave.bs_dates import BsDateService
from hajiriflow.db.models.calendar_leave import (
    FieldDutyRequest,
    Holiday,
    LeaveAllocation,
    LeavePolicy,
    LeaveRequest,
    OrganizationCalendarSettings,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.identity.audit import redact_audit_payload

ZERO = Decimal("0.00")
HALF = Decimal("0.50")
ONE = Decimal("1.00")


@dataclass(frozen=True, slots=True)
class WorkdayDecision:
    organization_id: UUID
    work_date: date
    calendar_working_day: bool
    attendance_expected: bool
    counts_as_present: bool
    reason: str
    reference_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LeaveBalance:
    entitlement: Decimal
    approved: Decimal
    pending: Decimal
    available: Decimal


class CalendarLeaveService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _audit(
        self,
        *,
        actor_user_id: UUID,
        action: str,
        object_type: str,
        object_id: UUID,
        after: dict,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                object_type=object_type,
                object_id=str(object_id),
                after_data=redact_audit_payload(after),
            )
        )

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

    def calendar_settings(self, organization_id: UUID) -> OrganizationCalendarSettings:
        self._company(organization_id)
        settings = self.session.get(OrganizationCalendarSettings, organization_id)
        if settings:
            return settings
        settings = OrganizationCalendarSettings(
            organization_id=organization_id,
            weekend_weekdays=[5],
        )
        self.session.add(settings)
        self.session.flush()
        return settings

    def set_weekends(
        self,
        *,
        organization_id: UUID,
        weekdays: list[int],
        actor_user_id: UUID,
    ) -> OrganizationCalendarSettings:
        if not weekdays or any(value < 0 or value > 6 for value in weekdays):
            raise ValueError("weekend weekdays must contain values from 0 through 6")
        values = sorted(set(weekdays))
        settings = self.calendar_settings(organization_id)
        settings.weekend_weekdays = values
        self._audit(
            actor_user_id=actor_user_id,
            action="calendar.weekends.updated",
            object_type="organization_calendar_settings",
            object_id=organization_id,
            after={"weekend_weekdays": values},
        )
        return settings

    def create_holiday(
        self,
        *,
        organization_id: UUID,
        holiday_date: date,
        name: str,
        category: str,
        paid: bool,
        actor_user_id: UUID,
    ) -> Holiday:
        self._company(organization_id)
        item = Holiday(
            organization_id=organization_id,
            holiday_date=holiday_date,
            name=name.strip(),
            category=category,
            paid=paid,
        )
        if not item.name:
            raise ValueError("holiday name cannot be blank")
        self.session.add(item)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="calendar.holiday.created",
            object_type="holiday",
            object_id=item.id,
            after={
                "holiday_date": holiday_date.isoformat(),
                "name": item.name,
                "category": category,
                "paid": paid,
            },
        )
        return item

    def list_holidays(
        self,
        organization_id: UUID,
        *,
        start_date: date,
        end_date: date,
    ) -> list[Holiday]:
        self._company(organization_id)
        if end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        query = (
            select(Holiday)
            .where(
                Holiday.organization_id == organization_id,
                Holiday.holiday_date >= start_date,
                Holiday.holiday_date <= end_date,
                Holiday.status == "active",
            )
            .order_by(Holiday.holiday_date, Holiday.name)
        )
        return list(self.session.scalars(query).all())

    def calendar_decision(self, organization_id: UUID, work_date: date) -> WorkdayDecision:
        settings = self.calendar_settings(organization_id)
        if work_date.weekday() in set(settings.weekend_weekdays):
            return WorkdayDecision(
                organization_id=organization_id,
                work_date=work_date,
                calendar_working_day=False,
                attendance_expected=False,
                counts_as_present=False,
                reason="weekend",
            )
        holiday = self.session.scalar(
            select(Holiday).where(
                Holiday.organization_id == organization_id,
                Holiday.holiday_date == work_date,
                Holiday.status == "active",
                Holiday.category != "optional",
            )
        )
        if holiday:
            return WorkdayDecision(
                organization_id=organization_id,
                work_date=work_date,
                calendar_working_day=False,
                attendance_expected=False,
                counts_as_present=False,
                reason="holiday",
                reference_id=holiday.id,
            )
        return WorkdayDecision(
            organization_id=organization_id,
            work_date=work_date,
            calendar_working_day=True,
            attendance_expected=True,
            counts_as_present=False,
            reason="workday",
        )

    def workday_decision(
        self,
        *,
        organization_id: UUID,
        work_date: date,
        employee_id: UUID | None = None,
    ) -> WorkdayDecision:
        calendar = self.calendar_decision(organization_id, work_date)
        if not calendar.calendar_working_day or not employee_id:
            return calendar
        self._employee(organization_id, employee_id)
        field_duty = self.session.scalar(
            select(FieldDutyRequest).where(
                FieldDutyRequest.organization_id == organization_id,
                FieldDutyRequest.employee_id == employee_id,
                FieldDutyRequest.status == "approved",
                FieldDutyRequest.start_date <= work_date,
                FieldDutyRequest.end_date >= work_date,
            )
        )
        if field_duty:
            return WorkdayDecision(
                organization_id=organization_id,
                work_date=work_date,
                calendar_working_day=True,
                attendance_expected=False,
                counts_as_present=True,
                reason="field_duty",
                reference_id=field_duty.id,
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
        if leave:
            return WorkdayDecision(
                organization_id=organization_id,
                work_date=work_date,
                calendar_working_day=True,
                attendance_expected=False,
                counts_as_present=False,
                reason="leave",
                reference_id=leave.id,
            )
        return calendar

    def working_days_between(
        self,
        *,
        organization_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        if end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        total = ZERO
        current = start_date
        while current <= end_date:
            if self.calendar_decision(organization_id, current).calendar_working_day:
                total += ONE
            current += timedelta(days=1)
        return total

    def create_leave_policy(
        self,
        *,
        organization_id: UUID,
        code: str,
        name: str,
        paid: bool,
        half_day_allowed: bool,
        annual_entitlement: Decimal,
        actor_user_id: UUID,
    ) -> LeavePolicy:
        self._company(organization_id)
        if annual_entitlement < ZERO:
            raise ValueError("annual entitlement cannot be negative")
        policy = LeavePolicy(
            organization_id=organization_id,
            code=code.strip().upper(),
            name=name.strip(),
            paid=paid,
            half_day_allowed=half_day_allowed,
            annual_entitlement=annual_entitlement,
        )
        if not policy.code or not policy.name:
            raise ValueError("leave policy code and name cannot be blank")
        self.session.add(policy)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="leave.policy.created",
            object_type="leave_policy",
            object_id=policy.id,
            after={
                "code": policy.code,
                "paid": paid,
                "half_day_allowed": half_day_allowed,
                "annual_entitlement": str(annual_entitlement),
            },
        )
        return policy

    def allocate_leave(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        period_year: int,
        allocated_days: Decimal,
        carried_days: Decimal,
        adjustment_days: Decimal,
        actor_user_id: UUID,
    ) -> LeaveAllocation:
        self._employee(organization_id, employee_id)
        policy = self.session.get(LeavePolicy, leave_policy_id)
        if not policy or policy.organization_id != organization_id:
            raise LookupError("leave policy not found")
        if allocated_days < ZERO or carried_days < ZERO:
            raise ValueError("allocated and carried days cannot be negative")
        allocation = self.session.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.leave_policy_id == leave_policy_id,
                LeaveAllocation.period_year == period_year,
            )
        )
        if not allocation:
            allocation = LeaveAllocation(
                organization_id=organization_id,
                employee_id=employee_id,
                leave_policy_id=leave_policy_id,
                period_year=period_year,
            )
            self.session.add(allocation)
        allocation.allocated_days = allocated_days
        allocation.carried_days = carried_days
        allocation.adjustment_days = adjustment_days
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="leave.allocation.updated",
            object_type="leave_allocation",
            object_id=allocation.id,
            after={
                "period_year": period_year,
                "allocated_days": str(allocated_days),
                "carried_days": str(carried_days),
                "adjustment_days": str(adjustment_days),
            },
        )
        return allocation

    def leave_balance(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        period_year: int,
        exclude_request_id: UUID | None = None,
    ) -> LeaveBalance:
        self._employee(organization_id, employee_id)
        allocation = self.session.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.leave_policy_id == leave_policy_id,
                LeaveAllocation.period_year == period_year,
            )
        )
        if not allocation:
            raise LookupError("leave allocation not found")
        entitlement = Decimal(allocation.allocated_days)
        entitlement += Decimal(allocation.carried_days)
        entitlement += Decimal(allocation.adjustment_days)
        period_start = BsDateService.bs_to_ad(f"{period_year:04d}-01-01")
        next_period_start = BsDateService.bs_to_ad(f"{period_year + 1:04d}-01-01")
        period_end = next_period_start - timedelta(days=1)
        base_filters = [
            LeaveRequest.organization_id == organization_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_policy_id == leave_policy_id,
            LeaveRequest.start_date >= period_start,
            LeaveRequest.start_date <= period_end,
        ]
        if exclude_request_id:
            base_filters.append(LeaveRequest.id != exclude_request_id)

        def used_for(status_value: str) -> Decimal:
            value = self.session.scalar(
                select(func.coalesce(func.sum(LeaveRequest.requested_days), 0)).where(
                    *base_filters,
                    LeaveRequest.status == status_value,
                )
            )
            return Decimal(value or 0).quantize(Decimal("0.01"))

        approved = used_for("approved")
        pending = used_for("pending")
        available = entitlement - approved - pending
        return LeaveBalance(
            entitlement=entitlement,
            approved=approved,
            pending=pending,
            available=available,
        )

    @staticmethod
    def _date_overlap(model, employee_id: UUID, start_date: date, end_date: date):
        return and_(
            model.employee_id == employee_id,
            model.start_date <= end_date,
            model.end_date >= start_date,
        )

    def request_leave(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        start_date: date,
        end_date: date,
        day_part: str,
        reason: str,
        requested_by: UUID,
    ) -> LeaveRequest:
        self._employee(organization_id, employee_id)
        if end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        start_bs_year = int(BsDateService.ad_to_bs(start_date).split("-", 1)[0])
        end_bs_year = int(BsDateService.ad_to_bs(end_date).split("-", 1)[0])
        if start_bs_year != end_bs_year:
            raise ValueError("leave requests cannot cross BS allocation years")
        policy = self.session.get(LeavePolicy, leave_policy_id)
        if not policy or policy.organization_id != organization_id or not policy.active:
            raise LookupError("leave policy not found")
        if day_part != "full":
            if start_date != end_date:
                raise ValueError("half-day leave must be a single date")
            if not policy.half_day_allowed:
                raise ValueError("this leave policy does not allow half days")
        overlap = self.session.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.organization_id == organization_id,
                self._date_overlap(LeaveRequest, employee_id, start_date, end_date),
                LeaveRequest.status.in_(("pending", "approved")),
            )
        )
        if overlap:
            raise ValueError("leave request overlaps an existing leave period")
        field_duty_overlap = self.session.scalar(
            select(FieldDutyRequest.id).where(
                FieldDutyRequest.organization_id == organization_id,
                self._date_overlap(FieldDutyRequest, employee_id, start_date, end_date),
                FieldDutyRequest.status.in_(("pending", "approved")),
            )
        )
        if field_duty_overlap:
            raise ValueError("leave request overlaps field duty")
        requested_days = self.working_days_between(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )
        if day_part != "full":
            if requested_days != ONE:
                raise ValueError("half-day leave must fall on a working day")
            requested_days = HALF
        if requested_days <= ZERO:
            raise ValueError("leave request contains no working days")
        balance = self.leave_balance(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=leave_policy_id,
            period_year=start_bs_year,
        )
        if requested_days > balance.available:
            raise ValueError("insufficient leave balance")
        request = LeaveRequest(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=leave_policy_id,
            start_date=start_date,
            end_date=end_date,
            day_part=day_part,
            requested_days=requested_days,
            reason=reason.strip(),
            requested_by=requested_by,
        )
        if not request.reason:
            raise ValueError("leave reason cannot be blank")
        self.session.add(request)
        self.session.flush()
        self._audit(
            actor_user_id=requested_by,
            action="leave.requested",
            object_type="leave_request",
            object_id=request.id,
            after={
                "employee_id": str(employee_id),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "day_part": day_part,
                "requested_days": str(requested_days),
            },
        )
        return request

    def decide_leave(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        decision: str,
        note: str | None,
        actor_user_id: UUID,
    ) -> LeaveRequest:
        request = self.session.get(LeaveRequest, request_id)
        if not request or request.organization_id != organization_id:
            raise LookupError("leave request not found")
        if request.status != "pending":
            raise ValueError("only pending leave requests can be decided")
        if decision not in {"approved", "rejected"}:
            raise ValueError("leave decision must be approved or rejected")
        if decision == "approved":
            request_bs_year = int(
                BsDateService.ad_to_bs(request.start_date).split("-", 1)[0]
            )
            balance = self.leave_balance(
                organization_id=organization_id,
                employee_id=request.employee_id,
                leave_policy_id=request.leave_policy_id,
                period_year=request_bs_year,
                exclude_request_id=request.id,
            )
            if request.requested_days > balance.available:
                raise ValueError("insufficient leave balance at approval time")
        request.status = decision
        request.decision_note = note.strip() if note else None
        request.decided_by = actor_user_id
        request.decided_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            action=f"leave.{decision}",
            object_type="leave_request",
            object_id=request.id,
            after={"status": decision, "decision_note": request.decision_note},
        )
        return request

    def request_field_duty(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        start_date: date,
        end_date: date,
        paid: bool,
        reason: str,
        requested_by: UUID,
    ) -> FieldDutyRequest:
        self._employee(organization_id, employee_id)
        if end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        leave_overlap = self.session.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.organization_id == organization_id,
                self._date_overlap(LeaveRequest, employee_id, start_date, end_date),
                LeaveRequest.status.in_(("pending", "approved")),
            )
        )
        if leave_overlap:
            raise ValueError("field duty overlaps leave")
        existing = self.session.scalar(
            select(FieldDutyRequest.id).where(
                FieldDutyRequest.organization_id == organization_id,
                self._date_overlap(FieldDutyRequest, employee_id, start_date, end_date),
                FieldDutyRequest.status.in_(("pending", "approved")),
            )
        )
        if existing:
            raise ValueError("field duty overlaps an existing request")
        request = FieldDutyRequest(
            organization_id=organization_id,
            employee_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            paid=paid,
            reason=reason.strip(),
            requested_by=requested_by,
        )
        if not request.reason:
            raise ValueError("field-duty reason cannot be blank")
        self.session.add(request)
        self.session.flush()
        self._audit(
            actor_user_id=requested_by,
            action="field_duty.requested",
            object_type="field_duty_request",
            object_id=request.id,
            after={
                "employee_id": str(employee_id),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "paid": paid,
            },
        )
        return request

    def decide_field_duty(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        decision: str,
        note: str | None,
        actor_user_id: UUID,
    ) -> FieldDutyRequest:
        request = self.session.get(FieldDutyRequest, request_id)
        if not request or request.organization_id != organization_id:
            raise LookupError("field-duty request not found")
        if request.status != "pending":
            raise ValueError("only pending field-duty requests can be decided")
        if decision not in {"approved", "rejected"}:
            raise ValueError("field-duty decision must be approved or rejected")
        request.status = decision
        request.decision_note = note.strip() if note else None
        request.decided_by = actor_user_id
        request.decided_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            action=f"field_duty.{decision}",
            object_type="field_duty_request",
            object_id=request.id,
            after={"status": decision, "decision_note": request.decision_note},
        )
        return request

    def list_employee_leave_requests(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        limit: int = 100,
    ) -> list[LeaveRequest]:
        self._employee(organization_id, employee_id)
        query = (
            select(LeaveRequest)
            .where(
                LeaveRequest.organization_id == organization_id,
                LeaveRequest.employee_id == employee_id,
            )
            .order_by(LeaveRequest.requested_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query).all())

    def list_employee_field_duty_requests(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        limit: int = 100,
    ) -> list[FieldDutyRequest]:
        self._employee(organization_id, employee_id)
        query = (
            select(FieldDutyRequest)
            .where(
                FieldDutyRequest.organization_id == organization_id,
                FieldDutyRequest.employee_id == employee_id,
            )
            .order_by(FieldDutyRequest.requested_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query).all())
