from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.db.models.payroll import PayrollLine, PayrollPeriod, PayrollRun
from hajiriflow.db.models.payroll_baseline import (
    DeductionType,
    EarningHead,
    EmployeeCompensationComponent,
    EmployeeCompensationProfile,
    FiscalYear,
    HolidayOvertimeRule,
    PayrollAdjustment,
    PayrollAttendanceReview,
    TaxSlab,
    TaxSlabSet,
)
from hajiriflow.payroll.baseline import PayrollBaselineService
from hajiriflow.reporting.exports import pdf_bytes

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/payroll-v2",
    tags=["payroll-v2"],
)


class FiscalYearCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    bs_start_year: int = Field(ge=2000)
    bs_end_year: int = Field(ge=2000)
    starts_on: date
    ends_on: date


class FiscalYearTransition(BaseModel):
    status: Literal["active", "closed", "locked"]


class EarningHeadCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    calculation_type: Literal["fixed", "percentage"]
    payment_frequency: Literal["monthly", "annual", "one_time"] = "monthly"
    taxable: bool = True


class DeductionTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    calculation_type: Literal["fixed", "percentage"]
    payment_frequency: Literal["monthly", "annual", "one_time"] = "monthly"
    pretax: bool = False
    enrollment_required: bool = False
    cap_amount: Decimal | None = Field(default=None, ge=0)


class CompensationProfileCreate(BaseModel):
    employee_id: UUID
    base_salary: Decimal = Field(ge=0)
    tax_category: str = Field(min_length=1, max_length=60)
    overtime_eligible: bool = True
    standard_monthly_minutes: int = Field(default=12480, gt=0)
    starts_on: date
    ends_on: date | None = None


class CompensationComponentCreate(BaseModel):
    component_type: Literal["earning", "deduction"]
    catalog_id: UUID
    value: Decimal = Field(ge=0)


class HolidayOvertimeRuleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    scope_type: Literal["organization", "employee"]
    employee_id: UUID | None = None
    multiplier: Decimal = Field(ge=1)
    starts_on: date
    ends_on: date | None = None


class TaxSlabInput(BaseModel):
    lower_bound: Decimal = Field(ge=0)
    upper_bound: Decimal | None = Field(default=None, gt=0)
    rate: Decimal = Field(ge=0, le=1)


class TaxSlabSetCreate(BaseModel):
    fiscal_year_id: UUID
    taxpayer_category: str = Field(min_length=1, max_length=60)
    version: str = Field(min_length=1, max_length=60)
    standard_deduction: Decimal = Field(default=Decimal("0"), ge=0)
    slabs: list[TaxSlabInput] = Field(min_length=1)


class PayrollPeriodCreate(BaseModel):
    fiscal_year_id: UUID
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    starts_on: date
    ends_on: date
    attendance_calculation_version: str = Field(default="attendance-v2", min_length=1)


class AttendanceReviewPrepare(BaseModel):
    period_id: UUID
    employee_id: UUID


class AttendanceReviewDecision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=2000)


class PayrollPreviewRequest(BaseModel):
    period_id: UUID
    employee_id: UUID


class PayrollGenerateRequest(BaseModel):
    period_id: UUID
    employee_ids: list[UUID] = Field(min_length=1, max_length=1000)
    calculation_version: str = Field(default="payroll-v2", min_length=1, max_length=80)


class PayrollAdjustmentCreate(BaseModel):
    employee_id: UUID
    adjustment_type: Literal["earning", "deduction"]
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)


class TaxProjectionRequest(BaseModel):
    fiscal_year_id: UUID
    employee_id: UUID
    projected_taxable_income: Decimal = Field(ge=0)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _fiscal_year(item: FiscalYear) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "label": item.label,
        "bs_start_year": item.bs_start_year,
        "bs_end_year": item.bs_end_year,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "status": item.status,
        "created_by": item.created_by,
        "activated_by": item.activated_by,
        "closed_by": item.closed_by,
        "locked_by": item.locked_by,
    }


def _earning_head(item: EarningHead) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "calculation_type": item.calculation_type,
        "payment_frequency": item.payment_frequency,
        "taxable": item.taxable,
        "active": item.active,
    }


def _deduction_type(item: DeductionType) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "calculation_type": item.calculation_type,
        "payment_frequency": item.payment_frequency,
        "pretax": item.pretax,
        "enrollment_required": item.enrollment_required,
        "cap_amount": item.cap_amount,
        "active": item.active,
    }


def _profile(item: EmployeeCompensationProfile) -> dict:
    return {
        "id": item.id,
        "employee_id": item.employee_id,
        "base_salary": item.base_salary,
        "tax_category": item.tax_category,
        "overtime_eligible": item.overtime_eligible,
        "standard_monthly_minutes": item.standard_monthly_minutes,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "active": item.active,
    }


def _component(item: EmployeeCompensationComponent) -> dict:
    return {
        "id": item.id,
        "compensation_profile_id": item.compensation_profile_id,
        "component_type": item.component_type,
        "earning_head_id": item.earning_head_id,
        "deduction_type_id": item.deduction_type_id,
        "value": item.value,
        "active": item.active,
    }


def _ot_rule(item: HolidayOvertimeRule) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "scope_type": item.scope_type,
        "employee_id": item.employee_id,
        "multiplier": item.multiplier,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "active": item.active,
    }


def _tax_policy(session: Session, item: TaxSlabSet) -> dict:
    slabs = session.scalars(
        select(TaxSlab)
        .where(TaxSlab.tax_slab_set_id == item.id)
        .order_by(TaxSlab.sequence)
    ).all()
    return {
        "id": item.id,
        "fiscal_year_id": item.fiscal_year_id,
        "taxpayer_category": item.taxpayer_category,
        "version": item.version,
        "status": item.status,
        "standard_deduction": item.standard_deduction,
        "created_by": item.created_by,
        "confirmed_by": item.confirmed_by,
        "slabs": [
            {
                "sequence": slab.sequence,
                "lower_bound": slab.lower_bound,
                "upper_bound": slab.upper_bound,
                "rate": slab.rate,
            }
            for slab in slabs
        ],
    }


def _period(item: PayrollPeriod) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "label": item.label,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "status": item.status,
        "attendance_calculation_version": item.attendance_calculation_version,
    }


def _review(item: PayrollAttendanceReview) -> dict:
    return {
        "id": item.id,
        "period_id": item.period_id,
        "employee_id": item.employee_id,
        "status": item.status,
        "attendance_snapshot": item.attendance_snapshot,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
    }


def _run(item: PayrollRun) -> dict:
    return {
        "id": item.id,
        "period_id": item.period_id,
        "sequence": item.sequence,
        "status": item.status,
        "calculation_version": item.calculation_version,
        "policy_snapshot": item.policy_snapshot,
        "created_by": item.created_by,
    }


def _adjustment(item: PayrollAdjustment) -> dict:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "employee_id": item.employee_id,
        "adjustment_type": item.adjustment_type,
        "amount": item.amount,
        "reason": item.reason,
        "created_by": item.created_by,
    }


@router.get("/fiscal-years")
def list_fiscal_years(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = session.scalars(
        select(FiscalYear)
        .where(FiscalYear.organization_id == organization_id)
        .order_by(FiscalYear.starts_on.desc())
    ).all()
    return [_fiscal_year(row) for row in rows]


@router.post("/fiscal-years", status_code=status.HTTP_201_CREATED)
def create_fiscal_year(
    organization_id: UUID,
    payload: FiscalYearCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_fiscal_year(
            organization_id=organization_id,
            code=payload.code,
            label=payload.label,
            bs_start_year=payload.bs_start_year,
            bs_end_year=payload.bs_end_year,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _fiscal_year(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/fiscal-years/{fiscal_year_id}/transition")
def transition_fiscal_year(
    organization_id: UUID,
    fiscal_year_id: UUID,
    payload: FiscalYearTransition,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).transition_fiscal_year(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            target_status=payload.status,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _fiscal_year(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/earning-heads")
def list_earning_heads(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    active: Annotated[bool | None, Query()] = None,
) -> list[dict]:
    query = select(EarningHead).where(EarningHead.organization_id == organization_id)
    if active is not None:
        query = query.where(EarningHead.active.is_(active))
    return [_earning_head(row) for row in session.scalars(query.order_by(EarningHead.code)).all()]


@router.post("/earning-heads", status_code=status.HTTP_201_CREATED)
def create_earning_head(
    organization_id: UUID,
    payload: EarningHeadCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_earning_head(
            organization_id=organization_id,
            code=payload.code,
            name=payload.name,
            calculation_type=payload.calculation_type,
            payment_frequency=payload.payment_frequency,
            taxable=payload.taxable,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _earning_head(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/deduction-types")
def list_deduction_types(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    active: Annotated[bool | None, Query()] = None,
) -> list[dict]:
    query = select(DeductionType).where(DeductionType.organization_id == organization_id)
    if active is not None:
        query = query.where(DeductionType.active.is_(active))
    rows = session.scalars(query.order_by(DeductionType.code)).all()
    return [_deduction_type(row) for row in rows]


@router.post("/deduction-types", status_code=status.HTTP_201_CREATED)
def create_deduction_type(
    organization_id: UUID,
    payload: DeductionTypeCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_deduction_type(
            organization_id=organization_id,
            code=payload.code,
            name=payload.name,
            calculation_type=payload.calculation_type,
            payment_frequency=payload.payment_frequency,
            pretax=payload.pretax,
            enrollment_required=payload.enrollment_required,
            cap_amount=payload.cap_amount,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _deduction_type(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/compensation", status_code=status.HTTP_201_CREATED)
def create_compensation_profile(
    organization_id: UUID,
    payload: CompensationProfileCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_compensation_profile(
            organization_id=organization_id,
            employee_id=payload.employee_id,
            base_salary=payload.base_salary,
            tax_category=payload.tax_category,
            overtime_eligible=payload.overtime_eligible,
            standard_monthly_minutes=payload.standard_monthly_minutes,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _profile(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/compensation/{profile_id}/components", status_code=status.HTTP_201_CREATED)
def add_compensation_component(
    organization_id: UUID,
    profile_id: UUID,
    payload: CompensationComponentCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).add_compensation_component(
            organization_id=organization_id,
            compensation_profile_id=profile_id,
            component_type=payload.component_type,
            catalog_id=payload.catalog_id,
            value=payload.value,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _component(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/holiday-overtime-rules", status_code=status.HTTP_201_CREATED)
def create_holiday_overtime_rule(
    organization_id: UUID,
    payload: HolidayOvertimeRuleCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_holiday_overtime_rule(
            organization_id=organization_id,
            code=payload.code,
            name=payload.name,
            scope_type=payload.scope_type,
            employee_id=payload.employee_id,
            multiplier=payload.multiplier,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _ot_rule(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/tax-policies", status_code=status.HTTP_201_CREATED)
def create_tax_policy(
    organization_id: UUID,
    payload: TaxSlabSetCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_tax_slab_set(
            organization_id=organization_id,
            fiscal_year_id=payload.fiscal_year_id,
            taxpayer_category=payload.taxpayer_category,
            version=payload.version,
            standard_deduction=payload.standard_deduction,
            slabs=(
                (slab.lower_bound, slab.upper_bound, slab.rate)
                for slab in payload.slabs
            ),
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _tax_policy(session, item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/tax-policies/{tax_policy_id}/confirm")
def confirm_tax_policy(
    organization_id: UUID,
    tax_policy_id: UUID,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).confirm_tax_slab_set(
            organization_id=organization_id,
            tax_slab_set_id=tax_policy_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _tax_policy(session, item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/periods", status_code=status.HTTP_201_CREATED)
def create_payroll_period(
    organization_id: UUID,
    payload: PayrollPeriodCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).create_period(
            organization_id=organization_id,
            fiscal_year_id=payload.fiscal_year_id,
            code=payload.code,
            label=payload.label,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            attendance_calculation_version=payload.attendance_calculation_version,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _period(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/attendance-reviews/prepare", status_code=status.HTTP_201_CREATED)
def prepare_attendance_review(
    organization_id: UUID,
    payload: AttendanceReviewPrepare,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).prepare_attendance_review(
            organization_id=organization_id,
            period_id=payload.period_id,
            employee_id=payload.employee_id,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _review(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/attendance-reviews/{review_id}/decision")
def decide_attendance_review(
    organization_id: UUID,
    review_id: UUID,
    payload: AttendanceReviewDecision,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.approve")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).decide_attendance_review(
            organization_id=organization_id,
            review_id=review_id,
            approve=payload.approve,
            note=payload.note,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _review(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/preview")
def preview_payroll(
    organization_id: UUID,
    payload: PayrollPreviewRequest,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return PayrollBaselineService(session).preview_employee(
            organization_id=organization_id,
            period_id=payload.period_id,
            employee_id=payload.employee_id,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_payroll(
    organization_id: UUID,
    payload: PayrollGenerateRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).generate_run(
            organization_id=organization_id,
            period_id=payload.period_id,
            employee_ids=payload.employee_ids,
            calculation_version=payload.calculation_version,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _run(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/runs/{run_id}/adjustments", status_code=status.HTTP_201_CREATED)
def add_payroll_adjustment(
    organization_id: UUID,
    run_id: UUID,
    payload: PayrollAdjustmentCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        item = PayrollBaselineService(session).add_adjustment(
            organization_id=organization_id,
            run_id=run_id,
            employee_id=payload.employee_id,
            adjustment_type=payload.adjustment_type,
            amount=payload.amount,
            reason=payload.reason,
            actor_user_id=identity.principal.user.id,
            grants=identity.principal.grants,
        )
        return _adjustment(item)
    except (LookupError, ValueError, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/tax-projection")
def tax_projection(
    organization_id: UUID,
    payload: TaxProjectionRequest,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    try:
        return PayrollBaselineService(session).tax_projection(
            organization_id=organization_id,
            fiscal_year_id=payload.fiscal_year_id,
            employee_id=payload.employee_id,
            projected_taxable_income=payload.projected_taxable_income,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/payslips/{line_id}")
def get_payslip(
    organization_id: UUID,
    line_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return PayrollBaselineService(session).payslip_payload(
            organization_id=organization_id,
            line_id=line_id,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/payslips/{line_id}.pdf")
def get_payslip_pdf(
    organization_id: UUID,
    line_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        content = PayrollBaselineService(session).payslip_pdf(
            organization_id=organization_id,
            line_id=line_id,
        )
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="payslip-{line_id}.pdf"'},
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/runs/{run_id}/payslips.pdf")
def get_batch_payslips_pdf(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    run = session.get(PayrollRun, run_id)
    if run is None or run.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="payroll run not found")
    if run.status not in {"posted", "reversed"}:
        raise HTTPException(status_code=400, detail="payslips require posted payroll")
    lines = session.scalars(
        select(PayrollLine)
        .where(PayrollLine.run_id == run.id)
        .order_by(PayrollLine.employee_id)
    ).all()
    content = pdf_bytes(
        title="HajiriFlow batch payslips",
        headers=("Employee", "Gross", "Deductions", "Tax", "Net", "Currency"),
        rows=(
            (
                line.employee_snapshot.get("employee_code", str(line.employee_id)),
                line.gross_amount,
                line.deduction_amount,
                line.tax_amount,
                line.net_amount,
                line.currency,
            )
            for line in lines
        ),
        metadata=(("Run ID", run.id),),
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="payroll-{run.id}.pdf"'},
    )


@router.get("/annual-summary/{fiscal_year_id}")
def annual_summary(
    organization_id: UUID,
    fiscal_year_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
) -> list[dict[str, str]]:
    return PayrollBaselineService(session).annual_summary(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        employee_id=employee_id,
    )


@router.get("/annual-summary/{fiscal_year_id}.xlsx")
def annual_summary_xlsx(
    organization_id: UUID,
    fiscal_year_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.export")),
    ],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Annotated[UUID | None, Query()] = None,
) -> Response:
    content = PayrollBaselineService(session).annual_summary_xlsx(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        employee_id=employee_id,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="annual-payroll.xlsx"'},
    )


def _self_employee(identity: RequestIdentity, organization_id: UUID, session: Session) -> UUID:
    employee_id = identity.principal.user.employee_id
    if employee_id is None:
        raise HTTPException(status_code=403, detail="account is not linked to an employee")
    employee = session.get(__import__("hajiriflow.db.models.workforce", fromlist=["Employee"]).Employee, employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="employee link is outside organization scope")
    return employee_id


@router.get("/self/payslips")
def self_payslips(
    organization_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    employee_id = _self_employee(identity, organization_id, session)
    service = PayrollBaselineService(session)
    return [
        service.payslip_payload(
            organization_id=organization_id,
            line_id=line.id,
            employee_id=employee_id,
        )
        for line, _run_item, _period_item in service.posted_lines(
            organization_id=organization_id,
            employee_id=employee_id,
        )
    ]


@router.get("/self/payslips/{line_id}")
def self_payslip(
    organization_id: UUID,
    line_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    employee_id = _self_employee(identity, organization_id, session)
    try:
        return PayrollBaselineService(session).payslip_payload(
            organization_id=organization_id,
            line_id=line_id,
            employee_id=employee_id,
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/self/payslips/{line_id}.pdf")
def self_payslip_pdf(
    organization_id: UUID,
    line_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    employee_id = _self_employee(identity, organization_id, session)
    try:
        content = PayrollBaselineService(session).payslip_pdf(
            organization_id=organization_id,
            line_id=line_id,
            employee_id=employee_id,
        )
        return Response(content=content, media_type="application/pdf")
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/self/annual-summary/{fiscal_year_id}")
def self_annual_summary(
    organization_id: UUID,
    fiscal_year_id: UUID,
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.self.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[dict[str, str]]:
    employee_id = _self_employee(identity, organization_id, session)
    return PayrollBaselineService(session).annual_summary(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        employee_id=employee_id,
    )
