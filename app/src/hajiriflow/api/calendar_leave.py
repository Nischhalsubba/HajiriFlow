from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    current_identity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.calendar_leave.bs_dates import BsDateService
from hajiriflow.calendar_leave.service import CalendarLeaveService
from hajiriflow.db.models.calendar_leave import (
    FieldDutyRequest,
    LeaveAllocation,
    LeavePolicy,
    LeaveRequest,
)

router = APIRouter(tags=["calendar-leave"])


class DateConversionView(BaseModel):
    ad_date: date
    bs_date: str


class BsMonthView(BaseModel):
    year: int
    month: int
    month_name: str
    days: int
    first_ad_date: date
    last_ad_date: date


class CalendarSettingsUpdate(BaseModel):
    weekend_weekdays: list[int] = Field(min_length=1, max_length=7)


class CalendarSettingsView(BaseModel):
    organization_id: UUID
    weekend_weekdays: list[int]


class HolidayCreate(BaseModel):
    holiday_date: date
    name: str = Field(min_length=1, max_length=200)
    category: Literal["public", "organization", "optional"]
    paid: bool = True


class HolidayView(BaseModel):
    id: UUID
    holiday_date: date
    name: str
    category: str
    paid: bool
    status: str


class WorkdayDecisionView(BaseModel):
    organization_id: UUID
    work_date: date
    calendar_working_day: bool
    attendance_expected: bool
    counts_as_present: bool
    reason: str
    reference_id: UUID | None


class LeavePolicyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    paid: bool = True
    half_day_allowed: bool = True
    annual_entitlement: Decimal = Field(ge=Decimal("0"), max_digits=8, decimal_places=2)


class LeavePolicyView(BaseModel):
    id: UUID
    code: str
    name: str
    paid: bool
    half_day_allowed: bool
    annual_entitlement: Decimal
    active: bool


class LeaveAllocationUpsert(BaseModel):
    employee_id: UUID
    leave_policy_id: UUID
    period_year: int = Field(ge=2000, le=2200)
    allocated_days: Decimal = Field(ge=Decimal("0"), max_digits=8, decimal_places=2)
    carried_days: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), max_digits=8, decimal_places=2
    )
    adjustment_days: Decimal = Field(
        default=Decimal("0"), max_digits=8, decimal_places=2
    )


class LeaveAllocationView(BaseModel):
    id: UUID
    employee_id: UUID
    leave_policy_id: UUID
    period_year: int
    allocated_days: Decimal
    carried_days: Decimal
    adjustment_days: Decimal


class LeaveBalanceView(BaseModel):
    entitlement: Decimal
    approved: Decimal
    pending: Decimal
    available: Decimal


class LeaveRequestCreate(BaseModel):
    leave_policy_id: UUID
    start_date: date
    end_date: date
    day_part: Literal["full", "first_half", "second_half"] = "full"
    reason: str = Field(min_length=1, max_length=2000)


class ManagedLeaveRequestCreate(LeaveRequestCreate):
    employee_id: UUID


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class LeaveRequestView(BaseModel):
    id: UUID
    employee_id: UUID
    leave_policy_id: UUID
    start_date: date
    end_date: date
    day_part: str
    requested_days: Decimal
    status: str
    reason: str
    decision_note: str | None


class FieldDutyCreate(BaseModel):
    start_date: date
    end_date: date
    paid: bool = True
    reason: str = Field(min_length=1, max_length=2000)


class ManagedFieldDutyCreate(FieldDutyCreate):
    employee_id: UUID


class FieldDutyDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class FieldDutyView(BaseModel):
    id: UUID
    employee_id: UUID
    start_date: date
    end_date: date
    paid: bool
    status: str
    reason: str
    decision_note: str | None


class DateConversionQuery(BaseModel):
    ad_date: date | None = None
    bs_date: str | None = None

    @model_validator(mode="after")
    def exactly_one_date(self):
        if (self.ad_date is None) == (self.bs_date is None):
            raise ValueError("provide exactly one of ad_date or bs_date")
        return self


def api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="record already exists")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def require_self_employee(identity: RequestIdentity) -> UUID:
    employee_id = identity.principal.user.employee_id
    if not employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="signed-in account is not linked to an employee",
        )
    return employee_id


def policy_view(item: LeavePolicy) -> LeavePolicyView:
    return LeavePolicyView(
        id=item.id,
        code=item.code,
        name=item.name,
        paid=item.paid,
        half_day_allowed=item.half_day_allowed,
        annual_entitlement=item.annual_entitlement,
        active=item.active,
    )


def allocation_view(item: LeaveAllocation) -> LeaveAllocationView:
    return LeaveAllocationView(
        id=item.id,
        employee_id=item.employee_id,
        leave_policy_id=item.leave_policy_id,
        period_year=item.period_year,
        allocated_days=item.allocated_days,
        carried_days=item.carried_days,
        adjustment_days=item.adjustment_days,
    )


def leave_view(item: LeaveRequest) -> LeaveRequestView:
    return LeaveRequestView(
        id=item.id,
        employee_id=item.employee_id,
        leave_policy_id=item.leave_policy_id,
        start_date=item.start_date,
        end_date=item.end_date,
        day_part=item.day_part,
        requested_days=item.requested_days,
        status=item.status,
        reason=item.reason,
        decision_note=item.decision_note,
    )


def field_duty_view(item: FieldDutyRequest) -> FieldDutyView:
    return FieldDutyView(
        id=item.id,
        employee_id=item.employee_id,
        start_date=item.start_date,
        end_date=item.end_date,
        paid=item.paid,
        status=item.status,
        reason=item.reason,
        decision_note=item.decision_note,
    )


@router.get("/api/v1/calendar/convert", response_model=DateConversionView)
def convert_date(
    _: Annotated[RequestIdentity, Depends(current_identity)],
    ad_date: Annotated[date | None, Query()] = None,
    bs_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
) -> DateConversionView:
    try:
        query = DateConversionQuery(ad_date=ad_date, bs_date=bs_date)
        if query.ad_date:
            return DateConversionView(
                ad_date=query.ad_date,
                bs_date=BsDateService.ad_to_bs(query.ad_date),
            )
        converted = BsDateService.bs_to_ad(query.bs_date or "")
        return DateConversionView(ad_date=converted, bs_date=query.bs_date or "")
    except ValueError as exc:
        raise api_error(exc) from exc


@router.get("/api/v1/calendar/bs-month/{year}/{month}", response_model=BsMonthView)
def bs_month_metadata(
    year: int,
    month: int,
    _: Annotated[RequestIdentity, Depends(current_identity)],
) -> BsMonthView:
    try:
        item = BsDateService.month_metadata(year, month)
        return BsMonthView(
            year=item.year,
            month=item.month,
            month_name=item.month_name,
            days=item.days,
            first_ad_date=item.first_ad_date,
            last_ad_date=item.last_ad_date,
        )
    except ValueError as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/calendar/settings",
    response_model=CalendarSettingsView,
)
def get_calendar_settings(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CalendarSettingsView:
    item = CalendarLeaveService(session).calendar_settings(organization_id)
    return CalendarSettingsView(
        organization_id=organization_id,
        weekend_weekdays=item.weekend_weekdays,
    )


@router.put(
    "/api/v1/organizations/{organization_id}/calendar/settings",
    response_model=CalendarSettingsView,
)
def update_calendar_settings(
    organization_id: UUID,
    payload: CalendarSettingsUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CalendarSettingsView:
    try:
        item = CalendarLeaveService(session).set_weekends(
            organization_id=organization_id,
            weekdays=payload.weekend_weekdays,
            actor_user_id=identity.principal.user.id,
        )
        return CalendarSettingsView(
            organization_id=organization_id,
            weekend_weekdays=item.weekend_weekdays,
        )
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/holidays",
    response_model=HolidayView,
    status_code=status.HTTP_201_CREATED,
)
def create_holiday(
    organization_id: UUID,
    payload: HolidayCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> HolidayView:
    try:
        item = CalendarLeaveService(session).create_holiday(
            organization_id=organization_id,
            holiday_date=payload.holiday_date,
            name=payload.name,
            category=payload.category,
            paid=payload.paid,
            actor_user_id=identity.principal.user.id,
        )
        return HolidayView(
            id=item.id,
            holiday_date=item.holiday_date,
            name=item.name,
            category=item.category,
            paid=item.paid,
            status=item.status,
        )
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/holidays",
    response_model=list[HolidayView],
)
def list_holidays(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
) -> list[HolidayView]:
    try:
        items = CalendarLeaveService(session).list_holidays(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )
        return [
            HolidayView(
                id=item.id,
                holiday_date=item.holiday_date,
                name=item.name,
                category=item.category,
                paid=item.paid,
                status=item.status,
            )
            for item in items
        ]
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/workday/{work_date}",
    response_model=WorkdayDecisionView,
)
def workday_decision(
    organization_id: UUID,
    work_date: date,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
) -> WorkdayDecisionView:
    try:
        item = CalendarLeaveService(session).workday_decision(
            organization_id=organization_id,
            work_date=work_date,
            employee_id=employee_id,
        )
        return WorkdayDecisionView(**item.__dict__)
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/policies",
    response_model=LeavePolicyView,
    status_code=status.HTTP_201_CREATED,
)
def create_leave_policy(
    organization_id: UUID,
    payload: LeavePolicyCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeavePolicyView:
    try:
        item = CalendarLeaveService(session).create_leave_policy(
            organization_id=organization_id,
            code=payload.code,
            name=payload.name,
            paid=payload.paid,
            half_day_allowed=payload.half_day_allowed,
            annual_entitlement=payload.annual_entitlement,
            actor_user_id=identity.principal.user.id,
        )
        return policy_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/leave/policies",
    response_model=list[LeavePolicyView],
)
def list_leave_policies(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("calendar.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[LeavePolicyView]:
    items = session.scalars(
        select(LeavePolicy)
        .where(
            LeavePolicy.organization_id == organization_id,
            LeavePolicy.active.is_(True),
        )
        .order_by(LeavePolicy.name)
    ).all()
    return [policy_view(item) for item in items]


@router.put(
    "/api/v1/organizations/{organization_id}/leave/allocations",
    response_model=LeaveAllocationView,
)
def upsert_leave_allocation(
    organization_id: UUID,
    payload: LeaveAllocationUpsert,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveAllocationView:
    try:
        item = CalendarLeaveService(session).allocate_leave(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            leave_policy_id=payload.leave_policy_id,
            period_year=payload.period_year,
            allocated_days=payload.allocated_days,
            carried_days=payload.carried_days,
            adjustment_days=payload.adjustment_days,
            actor_user_id=identity.principal.user.id,
        )
        return allocation_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/self/leave/balance/{leave_policy_id}/{period_year}",
    response_model=LeaveBalanceView,
)
def own_leave_balance(
    organization_id: UUID,
    leave_policy_id: UUID,
    period_year: int,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveBalanceView:
    try:
        employee_id = require_self_employee(identity)
        balance = CalendarLeaveService(session).leave_balance(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=leave_policy_id,
            period_year=period_year,
        )
        return LeaveBalanceView(**balance.__dict__)
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/self/leave/requests",
    response_model=LeaveRequestView,
    status_code=status.HTTP_201_CREATED,
)
def request_own_leave(
    organization_id: UUID,
    payload: LeaveRequestCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveRequestView:
    try:
        employee_id = require_self_employee(identity)
        item = CalendarLeaveService(session).request_leave(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_policy_id=payload.leave_policy_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            day_part=payload.day_part,
            reason=payload.reason,
            requested_by=identity.principal.user.id,
        )
        return leave_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/self/leave/requests",
    response_model=list[LeaveRequestView],
)
def own_leave_requests(
    organization_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[LeaveRequestView]:
    try:
        employee_id = require_self_employee(identity)
        items = CalendarLeaveService(session).list_employee_leave_requests(
            organization_id=organization_id,
            employee_id=employee_id,
        )
        return [leave_view(item) for item in items]
    except LookupError as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/requests",
    response_model=LeaveRequestView,
    status_code=status.HTTP_201_CREATED,
)
def request_managed_leave(
    organization_id: UUID,
    payload: ManagedLeaveRequestCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveRequestView:
    try:
        item = CalendarLeaveService(session).request_leave(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            leave_policy_id=payload.leave_policy_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            day_part=payload.day_part,
            reason=payload.reason,
            requested_by=identity.principal.user.id,
        )
        return leave_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/leave/requests/{request_id}/decision",
    response_model=LeaveRequestView,
)
def decide_leave(
    organization_id: UUID,
    request_id: UUID,
    payload: LeaveDecision,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("leave.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> LeaveRequestView:
    existing = session.get(LeaveRequest, request_id)
    if (
        existing
        and identity.principal.user.employee_id
        and existing.employee_id == identity.principal.user.employee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employees cannot approve or reject their own leave",
        )
    try:
        item = CalendarLeaveService(session).decide_leave(
            organization_id=organization_id,
            request_id=request_id,
            decision=payload.decision,
            note=payload.note,
            actor_user_id=identity.principal.user.id,
        )
        return leave_view(item)
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/self/field-duty/requests",
    response_model=FieldDutyView,
    status_code=status.HTTP_201_CREATED,
)
def request_own_field_duty(
    organization_id: UUID,
    payload: FieldDutyCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyView:
    try:
        employee_id = require_self_employee(identity)
        item = CalendarLeaveService(session).request_field_duty(
            organization_id=organization_id,
            employee_id=employee_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            paid=payload.paid,
            reason=payload.reason,
            requested_by=identity.principal.user.id,
        )
        return field_duty_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.get(
    "/api/v1/organizations/{organization_id}/self/field-duty/requests",
    response_model=list[FieldDutyView],
)
def own_field_duty_requests(
    organization_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.request")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[FieldDutyView]:
    try:
        employee_id = require_self_employee(identity)
        items = CalendarLeaveService(session).list_employee_field_duty_requests(
            organization_id=organization_id,
            employee_id=employee_id,
        )
        return [field_duty_view(item) for item in items]
    except LookupError as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/field-duty/requests",
    response_model=FieldDutyView,
    status_code=status.HTTP_201_CREATED,
)
def request_managed_field_duty(
    organization_id: UUID,
    payload: ManagedFieldDutyCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyView:
    try:
        item = CalendarLeaveService(session).request_field_duty(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            paid=payload.paid,
            reason=payload.reason,
            requested_by=identity.principal.user.id,
        )
        return field_duty_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise api_error(exc) from exc


@router.post(
    "/api/v1/organizations/{organization_id}/field-duty/requests/{request_id}/decision",
    response_model=FieldDutyView,
)
def decide_field_duty(
    organization_id: UUID,
    request_id: UUID,
    payload: FieldDutyDecision,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("field_duty.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> FieldDutyView:
    existing = session.get(FieldDutyRequest, request_id)
    if (
        existing
        and identity.principal.user.employee_id
        and existing.employee_id == identity.principal.user.employee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employees cannot approve or reject their own field duty",
        )
    try:
        item = CalendarLeaveService(session).decide_field_duty(
            organization_id=organization_id,
            request_id=request_id,
            decision=payload.decision,
            note=payload.note,
            actor_user_id=identity.principal.user.id,
        )
        return field_duty_view(item)
    except (LookupError, ValueError) as exc:
        raise api_error(exc) from exc
