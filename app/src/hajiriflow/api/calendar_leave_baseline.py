import csv
import io
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from hajiriflow.api.calendar_leave import (
    FieldDutyView,
    LeaveRequestView,
    field_duty_view,
    leave_view,
    require_self_employee,
)
from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.calendar_leave.baseline_service import (
    AnnualAllocationPlan,
    BsMonthCalendar,
    CalendarLeaveBaselineService,
    LeaveBalanceBreakdown,
)
from hajiriflow.db.models.calendar_leave import LeaveAllocation, LeavePolicy

router = APIRouter(tags=["calendar-leave-baseline"])

EmploymentType = Literal[
    "permanent",
    "contract",
    "temporary",
    "intern",
    "consultant",
]
RequestStatus = Literal["pending", "approved", "rejected", "cancelled"]


class HolidayUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: Literal["public", "organization", "optional"] | None = None
    paid: bool | None = None
    status: Literal["active", "cancelled"] | None = None


class HolidayBaselineView(BaseModel):
    id: UUID
    holiday_date: date
    name: str
    category: str
    paid: bool
    status: str


class PolicyRuleUpdate(BaseModel):
    carry_forward_allowed: bool = False
    carry_forward_cap: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )
    color_hex: str = Field(default="#2563EB", pattern=r"^#[0-9A-Fa-f]{6}$")
    eligibility_employment_types: list[EmploymentType] = Field(default_factory=list)
    active: bool = True


class PolicyRuleView(BaseModel):
    leave_policy_id: UUID
    code: str
    name: str
    paid: bool
    half_day_allowed: bool
    annual_entitlement: Decimal
    active: bool
    carry_forward_allowed: bool
    carry_forward_cap: Decimal | None
    color_hex: str
    eligibility_employment_types: list[str]


class AllocationBreakdownUpsert(BaseModel):
    employee_id: UUID
    leave_policy_id: UUID
    bs_year: int = Field(ge=1975, le=2200)
    opening_days: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )
    earned_days: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )
    carried_days: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )
    adjustment_days: Decimal = Field(
        default=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )


class AllocationBreakdownView(BaseModel):
    allocation_id: UUID
    employee_id: UUID
    leave_policy_id: UUID
    bs_year: int
    opening: Decimal
    earned: Decimal
    carried: Decimal
    adjustment: Decimal
    entitlement: Decimal
    used: Decimal
    pending: Decimal
    available: Decimal


class AnnualAllocationRequest(BaseModel):
    leave_policy_id: UUID
    bs_year: int = Field(ge=1975, le=2200)


class AnnualAllocationPlanView(BaseModel):
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


class BsCalendarDayView(BaseModel):
    bs_date: str
    ad_date: date
    working_day: bool
    reason: str
    holiday_name: str | None


class BsMonthCalendarView(BaseModel):
    bs_year: int
    bs_month: int
    month_name: str
    first_ad_date: date
    last_ad_date: date
    working_days: int
    days: list[BsCalendarDayView]


class WorkingDaysView(BaseModel):
    start_date: date
    end_date: date
    working_days: Decimal


class CancellationRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class EmployeeBalanceView(BaseModel):
    leave_policy_id: UUID
    code: str
    name: str
    paid: bool
    balance: AllocationBreakdownView


class FieldDutyDetailUpdate(BaseModel):
    location: str | None = Field(default=None, max_length=240)
    evidence_reference: str | None = Field(default=None, max_length=400)


class FieldDutyDetailedView(FieldDutyView):
    location: str | None
    evidence_reference: str | None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _policy_rule_view(
    policy: LeavePolicy,
    rule,
) -> PolicyRuleView:
    return PolicyRuleView(
        leave_policy_id=policy.id,
        code=policy.code,
        name=policy.name,
        paid=policy.paid,
        half_day_allowed=policy.half_day_allowed,
        annual_entitlement=policy.annual_entitlement,
        active=policy.active,
        carry_forward_allowed=rule.carry_forward_allowed,
        carry_forward_cap=rule.carry_forward_cap,
        color_hex=rule.color_hex,
        eligibility_employment_types=list(rule.eligibility_employment_types or []),
    )


def _balance_view(
    allocation: LeaveAllocation,
    balance: LeaveBalanceBreakdown,
) -> AllocationBreakdownView:
    return AllocationBreakdownView(
        allocation_id=allocation.id,
        employee_id=allocation.employee_id,
        leave_policy_id=allocation.leave_policy_id,
        bs_year=balance.bs_year,
        opening=balance.opening,
        earned=balance.earned,
        carried=balance.carried,
        adjustment=balance.adjustment,
        entitlement=balance.entitlement,
        used=balance.used,
        pending=balance.pending,
        available=balance.available,
    )


def _plan_view(item: AnnualAllocationPlan) -> AnnualAllocationPlanView:
    return AnnualAllocationPlanView(**asdict(item))


def _calendar_view(item: BsMonthCalendar) -> BsMonthCalendarView:
    return BsMonthCalendarView(
        bs_year=item.bs_year,
        bs_month=item.bs_month,
        month_name=item.month_name,
        first_ad_date=item.first_ad_date,
        last_ad_date=item.last_ad_date,
        working_days=item.working_days,
        days=[BsCalendarDayView(**asdict(day)) for day in item.days],
    )


@router.get(
    "/api/v1/organizations/{organization_id}/calendar/bs-month/{bs_year}/{bs_month}",
    response_model=BsMonthCalendarView,
)
def organization_bs_month(
    organization_id: UUID,
    bs_year: int,
    bs_month: int,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> BsMonthCalendarView:
    try:
        result = CalendarLeaveBaselineService(session).bs_month_calendar(
            organization_id=organization_id,
            bs_year=bs_year,
            bs_month=bs_month,
        )
        return _calendar_view(result)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/calendar/working-days",
    response_model=WorkingDaysView,
)
def organization_working_days(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
) -> WorkingDaysView:
    try:
        value = CalendarLeaveBaselineService(session).base.working_days_between(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )
        return WorkingDaysView(
            start_date=start_date,
            end_date=end_date,
            working_days=value,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.patch(
    "/api/v1/organizations/{organization_id}/holidays/{holiday_id}",
    response_model=HolidayBaselineView,
)
def update_holiday(
    organization_id: UUID,
    holiday_id: UUID,
    payload: HolidayUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> HolidayBaselineView:
    try:
        item = CalendarLeaveBaselineService(session).update_holiday(
            organization_id=organization_id,
            holiday_id=holiday_id,
            name=payload.name,
            category=payload.category,
            paid=payload.paid,
            status=payload.status,
            actor_user_id=identity.principal.user.id,
        )
        return HolidayBaselineView(
            id=item.id,
            holiday_date=item.holiday_date,
            name=item.name,
            category=item.category,
            paid=item.paid,
            status=item.status,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/leave/policies/{leave_policy_id}/rules",
    response_model=PolicyRuleView,
)
def get_policy_rules(
    organization_id: UUID,
    leave_policy_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PolicyRuleView:
    try:
        service = CalendarLeaveBaselineService(session)
        rule = service.policy_rule(organization_id, leave_policy_id)
        policy = session.get(LeavePolicy, leave_policy_id)
        if not policy:
            raise LookupError("leave policy not found")
        return _policy_rule_view(policy, rule)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.put(
    "/api/v1/organizations/{organization_id}/leave/policies/{leave_policy_id}/rules",
    response_model=PolicyRuleView,
)
def update_policy_rules(
    organization_id: UUID,
    leave_policy_id: UUID,
    payload: PolicyRuleUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PolicyRuleView:
    try:
        policy, rule = CalendarLeaveBaselineService(session).update_policy_rule(
            organization_id=organization_id,
            leave_policy_id=leave_policy_id,
            carry_forward_allowed=payload.carry_forward_allowed,
            carry_forward_cap=payload.carry_forward_cap,
            color_hex=payload.color_hex,
            eligibility_employment_types=list(payload.eligibility_employment_types),
            active=payload.active,
            actor_user_id=identity.principal.user.id,
        )
        return _policy_rule_view(policy, rule)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.put(
    "/api/v1/organizations/{organization_id}/leave/allocations/breakdown",
    response_model=AllocationBreakdownView,
)
def upsert_allocation_breakdown(
    organization_id: UUID,
    payload: AllocationBreakdownUpsert,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> AllocationBreakdownView:
    try:
        service = CalendarLeaveBaselineService(session)
        allocation = service.upsert_allocation_breakdown(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            leave_policy_id=payload.leave_policy_id,
            bs_year=payload.bs_year,
            opening_days=payload.opening_days,
            earned_days=payload.earned_days,
            carried_days=payload.carried_days,
            adjustment_days=payload.adjustment_days,
            source="manual",
            actor_user_id=identity.principal.user.id,
        )
        balance = service.balance_breakdown(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            leave_policy_id=payload.leave_policy_id,
            bs_year=payload.bs_year,
        )
        return _balance_view(allocation, balance)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/allocations/annual/preview",
    response_model=list[AnnualAllocationPlanView],
)
def preview_annual_allocation(
    organization_id: UUID,
    payload: AnnualAllocationRequest,
    _: Annotated[None, Depends(require_csrf)],
    __: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[AnnualAllocationPlanView]:
    try:
        items = CalendarLeaveBaselineService(session).annual_allocation_plan(
            organization_id=organization_id,
            leave_policy_id=payload.leave_policy_id,
            bs_year=payload.bs_year,
        )
        return [_plan_view(item) for item in items]
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/allocations/annual/apply",
    response_model=list[AnnualAllocationPlanView],
)
def apply_annual_allocation(
    organization_id: UUID,
    payload: AnnualAllocationRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[AnnualAllocationPlanView]:
    try:
        items = CalendarLeaveBaselineService(session).apply_annual_allocation(
            organization_id=organization_id,
            leave_policy_id=payload.leave_policy_id,
            bs_year=payload.bs_year,
            actor_user_id=identity.principal.user.id,
        )
        return [_plan_view(item) for item in items]
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/self/leave/balances/{bs_year}",
    response_model=list[EmployeeBalanceView],
)
def own_leave_balances(
    organization_id: UUID,
    bs_year: int,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[EmployeeBalanceView]:
    try:
        employee_id = require_self_employee(identity)
        service = CalendarLeaveBaselineService(session)
        results = service.employee_balances(
            organization_id=organization_id,
            employee_id=employee_id,
            bs_year=bs_year,
        )
        views: list[EmployeeBalanceView] = []
        for policy, balance in results:
            allocation = session.query(LeaveAllocation).filter_by(
                organization_id=organization_id,
                employee_id=employee_id,
                leave_policy_id=policy.id,
                period_year=bs_year,
            ).one()
            views.append(
                EmployeeBalanceView(
                    leave_policy_id=policy.id,
                    code=policy.code,
                    name=policy.name,
                    paid=policy.paid,
                    balance=_balance_view(allocation, balance),
                )
            )
        return views
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/self/leave/requests/{request_id}/cancel",
    response_model=LeaveRequestView,
)
def cancel_own_leave(
    organization_id: UUID,
    request_id: UUID,
    payload: CancellationRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveRequestView:
    try:
        item = CalendarLeaveBaselineService(session).cancel_leave(
            organization_id=organization_id,
            request_id=request_id,
            actor_user_id=identity.principal.user.id,
            employee_id=require_self_employee(identity),
            note=payload.note,
        )
        return leave_view(item)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/requests/{request_id}/cancel",
    response_model=LeaveRequestView,
)
def cancel_managed_leave(
    organization_id: UUID,
    request_id: UUID,
    payload: CancellationRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveRequestView:
    try:
        item = CalendarLeaveBaselineService(session).cancel_leave(
            organization_id=organization_id,
            request_id=request_id,
            actor_user_id=identity.principal.user.id,
            note=payload.note,
        )
        return leave_view(item)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/leave/requests",
    response_model=list[LeaveRequestView],
)
def managed_leave_requests(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[RequestStatus | None, Query(alias="status")] = None,
) -> list[LeaveRequestView]:
    items = CalendarLeaveBaselineService(session).list_leave_requests(
        organization_id=organization_id,
        employee_id=employee_id,
        status_filter=status_filter,
    )
    return [leave_view(item) for item in items]


@router.put(
    "/api/v1/organizations/{organization_id}/field-duty/requests/{request_id}/details",
    response_model=FieldDutyDetailedView,
)
def update_field_duty_details(
    organization_id: UUID,
    request_id: UUID,
    payload: FieldDutyDetailUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyDetailedView:
    try:
        request, detail = CalendarLeaveBaselineService(session).set_field_duty_detail(
            organization_id=organization_id,
            request_id=request_id,
            location=payload.location,
            evidence_reference=payload.evidence_reference,
            actor_user_id=identity.principal.user.id,
        )
        return FieldDutyDetailedView(
            **field_duty_view(request).model_dump(),
            location=detail.location,
            evidence_reference=detail.evidence_reference,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/self/field-duty/requests/{request_id}/cancel",
    response_model=FieldDutyView,
)
def cancel_own_field_duty(
    organization_id: UUID,
    request_id: UUID,
    payload: CancellationRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyView:
    try:
        item = CalendarLeaveBaselineService(session).cancel_field_duty(
            organization_id=organization_id,
            request_id=request_id,
            actor_user_id=identity.principal.user.id,
            employee_id=require_self_employee(identity),
            note=payload.note,
        )
        return field_duty_view(item)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/field-duty/requests/{request_id}/cancel",
    response_model=FieldDutyView,
)
def cancel_managed_field_duty(
    organization_id: UUID,
    request_id: UUID,
    payload: CancellationRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyView:
    try:
        item = CalendarLeaveBaselineService(session).cancel_field_duty(
            organization_id=organization_id,
            request_id=request_id,
            actor_user_id=identity.principal.user.id,
            note=payload.note,
        )
        return field_duty_view(item)
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


def _field_duty_detailed_view(item, detail) -> FieldDutyDetailedView:
    return FieldDutyDetailedView(
        **field_duty_view(item).model_dump(),
        location=detail.location if detail else None,
        evidence_reference=detail.evidence_reference if detail else None,
    )


@router.get(
    "/api/v1/organizations/{organization_id}/field-duty/requests",
    response_model=list[FieldDutyDetailedView],
)
def list_field_duty(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[RequestStatus | None, Query(alias="status")] = None,
    paid: Annotated[bool | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> list[FieldDutyDetailedView]:
    rows = CalendarLeaveBaselineService(session).list_field_duty(
        organization_id=organization_id,
        employee_id=employee_id,
        status_filter=status_filter,
        paid=paid,
        start_date=start_date,
        end_date=end_date,
    )
    return [_field_duty_detailed_view(item, detail) for item, detail in rows]


@router.get(
    "/api/v1/organizations/{organization_id}/field-duty/export/file",
)
def export_field_duty(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    export_format: Annotated[Literal["csv", "xlsx"], Query(alias="format")] = "csv",
    status_filter: Annotated[RequestStatus | None, Query(alias="status")] = None,
    paid: Annotated[bool | None, Query()] = None,
) -> StreamingResponse:
    rows = CalendarLeaveBaselineService(session).list_field_duty(
        organization_id=organization_id,
        status_filter=status_filter,
        paid=paid,
    )
    headers = [
        "employee_id",
        "start_date",
        "end_date",
        "paid",
        "status",
        "reason",
        "location",
        "evidence_reference",
    ]
    values = [
        [
            str(item.employee_id),
            item.start_date.isoformat(),
            item.end_date.isoformat(),
            item.paid,
            item.status,
            item.reason,
            detail.location if detail else None,
            detail.evidence_reference if detail else None,
        ]
        for item, detail in rows
    ]
    if export_format == "csv":
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(headers)
        writer.writerows(values)
        data = io.BytesIO(text.getvalue().encode("utf-8-sig"))
        media_type = "text/csv; charset=utf-8"
        filename = "field-duty.csv"
    else:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Field Duty")
        sheet.append(headers)
        for row in values:
            sheet.append(row)
        data = io.BytesIO()
        workbook.save(data)
        data.seek(0)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = "field-duty.xlsx"
    return StreamingResponse(
        data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
