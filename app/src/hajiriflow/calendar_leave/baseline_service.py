from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.calendar_leave.bs_dates import BsDateService
from hajiriflow.calendar_leave.service import CalendarLeaveService, LeaveBalance
from hajiriflow.db.models.calendar_leave import (
    FieldDutyRequest,
    Holiday,
    LeaveAllocation,
    LeavePolicy,
    LeaveRequest,
)
from hajiriflow.db.models.calendar_leave_baseline import (
    FieldDutyDetail,
    LeaveAllocationDetail,
    LeavePolicyRule,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import Employee
from hajiriflow.db.models.workforce_profile import EmployeeProfile
from hajiriflow.identity.audit import redact_audit_payload

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class BsCalendarDay:
    bs_date: str
    ad_date: date
    working_day: bool
    reason: str
    holiday_name: str | None


@dataclass(frozen=True, slots=True)
class BsMonthCalendar:
    bs_year: int
    bs_month: int
    month_name: str
    first_ad_date: date
    last_ad_date: date
    working_days: int
    days: tuple[BsCalendarDay, ...]


@dataclass(frozen=True, slots=True)
class LeaveBalanceBreakdown:
    bs_year: int
    opening: Decimal
    earned: Decimal
    carried: Decimal
    adjustment: Decimal
    entitlement: Decimal
    used: Decimal
    pending: Decimal
    available: Decimal


@dataclass(frozen=True, slots=True)
class AnnualAllocationPlan:
    employee_id: UUID
    employee_code: str
    employee_name: str
    employment_type: str
    eligible: bool
    skip_reason: str | None
    opening_days: Decimal
    earned_days: Decimal
    carried_days: Decimal
    adjustment_days: Decimal
    action: str
    allocation_id: UUID | None


class CalendarLeaveBaselineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.base = CalendarLeaveService(session)

    @staticmethod
    def bs_period_bounds(bs_year: int) -> tuple[date, date]:
        start = BsDateService.bs_to_ad(f"{bs_year:04d}-01-01")
        next_start = BsDateService.bs_to_ad(f"{bs_year + 1:04d}-01-01")
        return start, next_start - timedelta(days=1)

    @staticmethod
    def bs_year_for_date(value: date) -> int:
        return int(BsDateService.ad_to_bs(value).split("-", 1)[0])

    def _audit(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
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
                context_data={"organization_id": str(organization_id)},
            )
        )

    def policy_rule(
        self,
        organization_id: UUID,
        leave_policy_id: UUID,
    ) -> LeavePolicyRule:
        policy = self.session.get(LeavePolicy, leave_policy_id)
        if not policy or policy.organization_id != organization_id:
            raise LookupError("leave policy not found")
        item = self.session.get(LeavePolicyRule, leave_policy_id)
        if item:
            return item
        item = LeavePolicyRule(
            leave_policy_id=leave_policy_id,
            organization_id=organization_id,
            carry_forward_allowed=False,
            carry_forward_cap=None,
            color_hex="#2563EB",
            eligibility_employment_types=[],
        )
        self.session.add(item)
        self.session.flush()
        return item

    def update_policy_rule(
        self,
        *,
        organization_id: UUID,
        leave_policy_id: UUID,
        carry_forward_allowed: bool,
        carry_forward_cap: Decimal | None,
        color_hex: str,
        eligibility_employment_types: list[str],
        active: bool,
        actor_user_id: UUID,
    ) -> tuple[LeavePolicy, LeavePolicyRule]:
        policy = self.session.get(LeavePolicy, leave_policy_id)
        if not policy or policy.organization_id != organization_id:
            raise LookupError("leave policy not found")
        if carry_forward_cap is not None and carry_forward_cap < ZERO:
            raise ValueError("carry-forward cap cannot be negative")
        normalized_color = color_hex.strip().upper()
        if len(normalized_color) != 7 or not normalized_color.startswith("#"):
            raise ValueError("color must use #RRGGBB format")
        try:
            int(normalized_color[1:], 16)
        except ValueError as exc:
            raise ValueError("color must use #RRGGBB format") from exc
        allowed_types = {
            "permanent",
            "contract",
            "temporary",
            "intern",
            "consultant",
        }
        normalized_types = sorted(set(eligibility_employment_types))
        if any(item not in allowed_types for item in normalized_types):
            raise ValueError("unsupported employment type in leave eligibility")
        rule = self.policy_rule(organization_id, leave_policy_id)
        rule.carry_forward_allowed = carry_forward_allowed
        rule.carry_forward_cap = carry_forward_cap
        rule.color_hex = normalized_color
        rule.eligibility_employment_types = normalized_types
        rule.updated_at = datetime.now(UTC)
        policy.active = active
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="leave.policy.rules.updated",
            object_type="leave_policy",
            object_id=policy.id,
            after={
                "carry_forward_allowed": carry_forward_allowed,
                "carry_forward_cap": (
                    str(carry_forward_cap) if carry_forward_cap is not None else None
                ),
                "color_hex": normalized_color,
                "eligibility_employment_types": normalized_types,
                "active": active,
            },
        )
        return policy, rule

    def update_holiday(
        self,
        *,
        organization_id: UUID,
        holiday_id: UUID,
        name: str | None,
        category: str | None,
        paid: bool | None,
        status: str | None,
        actor_user_id: UUID,
    ) -> Holiday:
        item = self.session.get(Holiday, holiday_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("holiday not found")
        if name is not None:
            item.name = name.strip()
            if not item.name:
                raise ValueError("holiday name cannot be blank")
        if category is not None:
            item.category = category
        if paid is not None:
            item.paid = paid
        if status is not None:
            item.status = status
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="calendar.holiday.updated",
            object_type="holiday",
            object_id=item.id,
            after={
                "name": item.name,
                "category": item.category,
                "paid": item.paid,
                "status": item.status,
            },
        )
        return item

    def bs_month_calendar(
        self,
        *,
        organization_id: UUID,
        bs_year: int,
        bs_month: int,
    ) -> BsMonthCalendar:
        metadata = BsDateService.month_metadata(bs_year, bs_month)
        holidays = {
            item.holiday_date: item
            for item in self.base.list_holidays(
                organization_id,
                start_date=metadata.first_ad_date,
                end_date=metadata.last_ad_date,
            )
        }
        days: list[BsCalendarDay] = []
        working_days = 0
        current = metadata.first_ad_date
        while current <= metadata.last_ad_date:
            decision = self.base.calendar_decision(organization_id, current)
            if decision.calendar_working_day:
                working_days += 1
            holiday = holidays.get(current)
            days.append(
                BsCalendarDay(
                    bs_date=BsDateService.ad_to_bs(current),
                    ad_date=current,
                    working_day=decision.calendar_working_day,
                    reason=decision.reason,
                    holiday_name=holiday.name if holiday else None,
                )
            )
            current += timedelta(days=1)
        return BsMonthCalendar(
            bs_year=bs_year,
            bs_month=bs_month,
            month_name=metadata.month_name,
            first_ad_date=metadata.first_ad_date,
            last_ad_date=metadata.last_ad_date,
            working_days=working_days,
            days=tuple(days),
        )

    def allocation_detail(
        self,
        allocation: LeaveAllocation,
    ) -> LeaveAllocationDetail:
        item = self.session.get(LeaveAllocationDetail, allocation.id)
        if item:
            return item
        item = LeaveAllocationDetail(
            leave_allocation_id=allocation.id,
            organization_id=allocation.organization_id,
            opening_days=ZERO,
            earned_days=Decimal(allocation.allocated_days),
            source="manual",
        )
        self.session.add(item)
        self.session.flush()
        return item

    def upsert_allocation_breakdown(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        bs_year: int,
        opening_days: Decimal,
        earned_days: Decimal,
        carried_days: Decimal,
        adjustment_days: Decimal,
        source: str,
        actor_user_id: UUID,
    ) -> LeaveAllocation:
        if opening_days < ZERO or earned_days < ZERO or carried_days < ZERO:
            raise ValueError("opening, earned, and carried days cannot be negative")
        if source not in {"manual", "annual"}:
            raise ValueError("unsupported leave-allocation source")
        allocation = self.base.allocate_leave(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=leave_policy_id,
            period_year=bs_year,
            allocated_days=opening_days + earned_days,
            carried_days=carried_days,
            adjustment_days=adjustment_days,
            actor_user_id=actor_user_id,
        )
        detail = self.allocation_detail(allocation)
        detail.opening_days = opening_days
        detail.earned_days = earned_days
        detail.source = source
        detail.updated_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="leave.allocation.breakdown.updated",
            object_type="leave_allocation",
            object_id=allocation.id,
            after={
                "bs_year": bs_year,
                "opening_days": str(opening_days),
                "earned_days": str(earned_days),
                "carried_days": str(carried_days),
                "adjustment_days": str(adjustment_days),
                "source": source,
            },
        )
        return allocation

    def balance_breakdown(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        bs_year: int,
    ) -> LeaveBalanceBreakdown:
        allocation = self.session.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.organization_id == organization_id,
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.leave_policy_id == leave_policy_id,
                LeaveAllocation.period_year == bs_year,
            )
        )
        if not allocation:
            raise LookupError("leave allocation not found")
        detail = self.allocation_detail(allocation)
        balance: LeaveBalance = self.base.leave_balance(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=leave_policy_id,
            period_year=bs_year,
        )
        opening = Decimal(detail.opening_days)
        earned = Decimal(detail.earned_days)
        carried = Decimal(allocation.carried_days)
        adjustment = Decimal(allocation.adjustment_days)
        return LeaveBalanceBreakdown(
            bs_year=bs_year,
            opening=opening,
            earned=earned,
            carried=carried,
            adjustment=adjustment,
            entitlement=balance.entitlement,
            used=balance.approved,
            pending=balance.pending,
            available=balance.available,
        )

    def employee_balances(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        bs_year: int,
    ) -> list[tuple[LeavePolicy, LeaveBalanceBreakdown]]:
        self.base._employee(organization_id, employee_id)
        allocations = self.session.scalars(
            select(LeaveAllocation)
            .where(
                LeaveAllocation.organization_id == organization_id,
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.period_year == bs_year,
            )
            .order_by(LeaveAllocation.leave_policy_id)
        ).all()
        result: list[tuple[LeavePolicy, LeaveBalanceBreakdown]] = []
        for allocation in allocations:
            policy = self.session.get(LeavePolicy, allocation.leave_policy_id)
            if not policy:
                continue
            result.append(
                (
                    policy,
                    self.balance_breakdown(
                        organization_id=organization_id,
                        employee_id=employee_id,
                        leave_policy_id=allocation.leave_policy_id,
                        bs_year=bs_year,
                    ),
                )
            )
        return result

    def _carry_forward(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        leave_policy_id: UUID,
        bs_year: int,
        rule: LeavePolicyRule,
    ) -> Decimal:
        if not rule.carry_forward_allowed:
            return ZERO
        try:
            previous = self.balance_breakdown(
                organization_id=organization_id,
                employee_id=employee_id,
                leave_policy_id=leave_policy_id,
                bs_year=bs_year - 1,
            )
        except LookupError:
            return ZERO
        carried = max(previous.available, ZERO)
        if rule.carry_forward_cap is not None:
            carried = min(carried, Decimal(rule.carry_forward_cap))
        return carried

    def annual_allocation_plan(
        self,
        *,
        organization_id: UUID,
        leave_policy_id: UUID,
        bs_year: int,
    ) -> list[AnnualAllocationPlan]:
        policy = self.session.get(LeavePolicy, leave_policy_id)
        if not policy or policy.organization_id != organization_id:
            raise LookupError("leave policy not found")
        if not policy.active:
            raise ValueError("leave policy is inactive")
        rule = self.policy_rule(organization_id, leave_policy_id)
        period_start, period_end = self.bs_period_bounds(bs_year)
        rows = self.session.execute(
            select(Employee, EmployeeProfile)
            .outerjoin(EmployeeProfile, EmployeeProfile.employee_id == Employee.id)
            .where(
                Employee.organization_id == organization_id,
                Employee.status == "active",
                Employee.joined_on <= period_end,
            )
            .order_by(Employee.employee_code)
        ).all()
        plans: list[AnnualAllocationPlan] = []
        allowed = set(rule.eligibility_employment_types or [])
        for employee, profile in rows:
            if employee.left_on and employee.left_on < period_start:
                continue
            employment_type = profile.employment_type if profile else "permanent"
            eligible = not allowed or employment_type in allowed
            carried = ZERO
            earned = ZERO
            reason = None
            if eligible:
                carried = self._carry_forward(
                    organization_id=organization_id,
                    employee_id=employee.id,
                    leave_policy_id=leave_policy_id,
                    bs_year=bs_year,
                    rule=rule,
                )
                earned = Decimal(policy.annual_entitlement)
            else:
                reason = "employment type is not eligible for this leave policy"
            existing = self.session.scalar(
                select(LeaveAllocation).where(
                    LeaveAllocation.organization_id == organization_id,
                    LeaveAllocation.employee_id == employee.id,
                    LeaveAllocation.leave_policy_id == leave_policy_id,
                    LeaveAllocation.period_year == bs_year,
                )
            )
            adjustment = Decimal(existing.adjustment_days) if existing else ZERO
            action = "skipped"
            if eligible:
                if not existing:
                    action = "create"
                else:
                    detail = self.allocation_detail(existing)
                    same = (
                        Decimal(detail.opening_days) == ZERO
                        and Decimal(detail.earned_days) == earned
                        and Decimal(existing.carried_days) == carried
                    )
                    action = "no_change" if same else "update"
            plans.append(
                AnnualAllocationPlan(
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    employee_name=employee.display_name,
                    employment_type=employment_type,
                    eligible=eligible,
                    skip_reason=reason,
                    opening_days=ZERO,
                    earned_days=earned,
                    carried_days=carried,
                    adjustment_days=adjustment,
                    action=action,
                    allocation_id=existing.id if existing else None,
                )
            )
        return plans

    def apply_annual_allocation(
        self,
        *,
        organization_id: UUID,
        leave_policy_id: UUID,
        bs_year: int,
        actor_user_id: UUID,
    ) -> list[AnnualAllocationPlan]:
        plans = self.annual_allocation_plan(
            organization_id=organization_id,
            leave_policy_id=leave_policy_id,
            bs_year=bs_year,
        )
        for plan in plans:
            if not plan.eligible:
                continue
            self.upsert_allocation_breakdown(
                organization_id=organization_id,
                employee_id=plan.employee_id,
                leave_policy_id=leave_policy_id,
                bs_year=bs_year,
                opening_days=plan.opening_days,
                earned_days=plan.earned_days,
                carried_days=plan.carried_days,
                adjustment_days=plan.adjustment_days,
                source="annual",
                actor_user_id=actor_user_id,
            )
        self.session.flush()
        return self.annual_allocation_plan(
            organization_id=organization_id,
            leave_policy_id=leave_policy_id,
            bs_year=bs_year,
        )

    def cancel_leave(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        actor_user_id: UUID,
        employee_id: UUID | None = None,
        note: str | None = None,
    ) -> LeaveRequest:
        item = self.session.get(LeaveRequest, request_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("leave request not found")
        if employee_id is not None and item.employee_id != employee_id:
            raise LookupError("leave request not found")
        if item.status not in {"pending", "approved"}:
            raise ValueError("only pending or approved leave can be cancelled")
        item.status = "cancelled"
        item.decision_note = note.strip() if note else "Cancelled"
        item.decided_by = actor_user_id
        item.decided_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="leave.cancelled",
            object_type="leave_request",
            object_id=item.id,
            after={
                "status": "cancelled",
                "employee_id": str(item.employee_id),
                "requested_days": str(item.requested_days),
            },
        )
        return item

    def list_leave_requests(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None = None,
        status_filter: str | None = None,
        limit: int = 200,
    ) -> list[LeaveRequest]:
        query = select(LeaveRequest).where(
            LeaveRequest.organization_id == organization_id
        )
        if employee_id:
            query = query.where(LeaveRequest.employee_id == employee_id)
        if status_filter:
            query = query.where(LeaveRequest.status == status_filter)
        query = query.order_by(LeaveRequest.requested_at.desc()).limit(limit)
        return list(self.session.scalars(query).all())

    def set_field_duty_detail(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        location: str | None,
        evidence_reference: str | None,
        actor_user_id: UUID,
    ) -> tuple[FieldDutyRequest, FieldDutyDetail]:
        request = self.session.get(FieldDutyRequest, request_id)
        if not request or request.organization_id != organization_id:
            raise LookupError("field-duty request not found")
        detail = self.session.get(FieldDutyDetail, request_id)
        if not detail:
            detail = FieldDutyDetail(
                field_duty_request_id=request_id,
                organization_id=organization_id,
            )
            self.session.add(detail)
        detail.location = location.strip() if location and location.strip() else None
        detail.evidence_reference = (
            evidence_reference.strip()
            if evidence_reference and evidence_reference.strip()
            else None
        )
        detail.updated_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="field_duty.details.updated",
            object_type="field_duty_request",
            object_id=request.id,
            after={
                "location": detail.location,
                "evidence_reference": detail.evidence_reference,
            },
        )
        return request, detail

    def cancel_field_duty(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        actor_user_id: UUID,
        employee_id: UUID | None = None,
        note: str | None = None,
    ) -> FieldDutyRequest:
        item = self.session.get(FieldDutyRequest, request_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("field-duty request not found")
        if employee_id is not None and item.employee_id != employee_id:
            raise LookupError("field-duty request not found")
        if item.status not in {"pending", "approved"}:
            raise ValueError("only pending or approved field duty can be cancelled")
        item.status = "cancelled"
        item.decision_note = note.strip() if note else "Cancelled"
        item.decided_by = actor_user_id
        item.decided_at = datetime.now(UTC)
        self._audit(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="field_duty.cancelled",
            object_type="field_duty_request",
            object_id=item.id,
            after={"status": "cancelled", "employee_id": str(item.employee_id)},
        )
        return item

    def list_field_duty(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None = None,
        status_filter: str | None = None,
        paid: bool | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 500,
    ) -> list[tuple[FieldDutyRequest, FieldDutyDetail | None]]:
        query = (
            select(FieldDutyRequest, FieldDutyDetail)
            .outerjoin(
                FieldDutyDetail,
                FieldDutyDetail.field_duty_request_id == FieldDutyRequest.id,
            )
            .where(FieldDutyRequest.organization_id == organization_id)
        )
        if employee_id:
            query = query.where(FieldDutyRequest.employee_id == employee_id)
        if status_filter:
            query = query.where(FieldDutyRequest.status == status_filter)
        if paid is not None:
            query = query.where(FieldDutyRequest.paid == paid)
        if start_date:
            query = query.where(FieldDutyRequest.end_date >= start_date)
        if end_date:
            query = query.where(FieldDutyRequest.start_date <= end_date)
        query = query.order_by(FieldDutyRequest.start_date.desc()).limit(limit)
        return list(self.session.execute(query).all())
