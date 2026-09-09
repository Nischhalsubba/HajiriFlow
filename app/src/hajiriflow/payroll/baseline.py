from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import AttendanceRecordDetail
from hajiriflow.db.models.identity import AuditEvent
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
    PayrollPeriodContext,
    TaxSlab,
    TaxSlabSet,
)
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.identity.audit import redact_audit_payload
from hajiriflow.identity.permissions import PermissionGrant, has_permission
from hajiriflow.payroll.service import (
    PAYROLL_APPROVE,
    PAYROLL_MANAGE,
    PayrollService,
)
from hajiriflow.reporting.exports import pdf_bytes, workbook_bytes

MONEY = Decimal("0.01")
PERCENT = Decimal("100")
DEFAULT_ANNUAL_PERIODS = Decimal("12")
PAYROLL_SELF_READ = "payroll.self.read"


def utc_now() -> datetime:
    return datetime.now(UTC)


def money(value: Decimal | int | str) -> Decimal:
    result = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    if result < 0:
        raise ValueError("payroll amounts cannot be negative")
    return result


def _effective_range(starts_on: date, ends_on: date | None, target: date) -> bool:
    return starts_on <= target and (ends_on is None or ends_on >= target)


class PayrollBaselineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.lifecycle = PayrollService(session)

    @staticmethod
    def _require(
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
        permission: str,
        organization_id: UUID,
    ) -> None:
        if not has_permission(grants, permission, organization_id=organization_id):
            raise PermissionError(f"missing {permission} permission")

    def _organization(self, organization_id: UUID) -> CompanyProfile:
        item = self.session.get(CompanyProfile, organization_id)
        if item is None:
            raise LookupError("organization not found")
        return item

    def _employee(self, organization_id: UUID, employee_id: UUID) -> Employee:
        item = self.session.get(Employee, employee_id)
        if item is None or item.organization_id != organization_id:
            raise LookupError("employee not found")
        return item

    def _audit(
        self,
        *,
        organization_id: UUID,
        actor_user_id: UUID,
        action: str,
        object_type: str,
        object_id: UUID | str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                object_type=object_type,
                object_id=str(object_id),
                reason=reason,
                before_data=redact_audit_payload(before) if before else None,
                after_data=redact_audit_payload(after) if after else None,
                context_data={"organization_id": str(organization_id)},
            )
        )

    def create_fiscal_year(
        self,
        *,
        organization_id: UUID,
        code: str,
        label: str,
        bs_start_year: int,
        bs_end_year: int,
        starts_on: date,
        ends_on: date,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> FiscalYear:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._organization(organization_id)
        if ends_on < starts_on:
            raise ValueError("fiscal year end must be on or after its start")
        if bs_start_year < 2000 or bs_end_year < bs_start_year:
            raise ValueError("invalid Bikram Sambat fiscal-year range")
        overlap = self.session.scalar(
            select(FiscalYear.id).where(
                FiscalYear.organization_id == organization_id,
                FiscalYear.starts_on <= ends_on,
                FiscalYear.ends_on >= starts_on,
            )
        )
        if overlap:
            raise ValueError("fiscal years cannot overlap")
        item = FiscalYear(
            organization_id=organization_id,
            code=code.strip(),
            label=label.strip(),
            bs_start_year=bs_start_year,
            bs_end_year=bs_end_year,
            starts_on=starts_on,
            ends_on=ends_on,
            created_by=actor_user_id,
        )
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.fiscal_year.created",
            object_type="fiscal_year",
            object_id=item.id,
            after={"code": item.code, "status": item.status},
        )
        return item

    def transition_fiscal_year(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        target_status: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> FiscalYear:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        item = self.session.get(FiscalYear, fiscal_year_id)
        if item is None or item.organization_id != organization_id:
            raise LookupError("fiscal year not found")
        transitions = {
            "upcoming": "active",
            "active": "closed",
            "closed": "locked",
        }
        if transitions.get(item.status) != target_status:
            raise ValueError(f"fiscal year cannot transition from {item.status} to {target_status}")
        if target_status == "active":
            active = self.session.scalar(
                select(FiscalYear.id).where(
                    FiscalYear.organization_id == organization_id,
                    FiscalYear.status == "active",
                    FiscalYear.id != item.id,
                )
            )
            if active:
                raise ValueError("organization already has an active fiscal year")
            if item.created_by == actor_user_id:
                raise ValueError("fiscal-year activation requires independent approval")
            item.activated_by = actor_user_id
            item.activated_at = utc_now()
        elif target_status == "closed":
            open_period = self.session.scalar(
                select(PayrollPeriod.id)
                .join(PayrollPeriodContext, PayrollPeriodContext.period_id == PayrollPeriod.id)
                .where(
                    PayrollPeriodContext.fiscal_year_id == item.id,
                    PayrollPeriod.status != "closed",
                )
                .limit(1)
            )
            if open_period:
                raise ValueError("all payroll periods must be closed before the fiscal year")
            item.closed_by = actor_user_id
            item.closed_at = utc_now()
        else:
            item.locked_by = actor_user_id
            item.locked_at = utc_now()
        before = {"status": item.status}
        item.status = target_status
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=f"payroll.fiscal_year.{target_status}",
            object_type="fiscal_year",
            object_id=item.id,
            before=before,
            after={"status": item.status},
        )
        return item

    def create_earning_head(
        self,
        *,
        organization_id: UUID,
        code: str,
        name: str,
        calculation_type: str,
        payment_frequency: str,
        taxable: bool,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> EarningHead:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._organization(organization_id)
        if calculation_type not in {"fixed", "percentage"}:
            raise ValueError("earning calculation type must be fixed or percentage")
        if payment_frequency not in {"monthly", "annual", "one_time"}:
            raise ValueError("unsupported earning payment frequency")
        item = EarningHead(
            organization_id=organization_id,
            code=code.strip(),
            name=name.strip(),
            calculation_type=calculation_type,
            payment_frequency=payment_frequency,
            taxable=taxable,
        )
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.earning_head.created",
            object_type="earning_head",
            object_id=item.id,
            after={"code": item.code, "calculation_type": calculation_type},
        )
        return item

    def create_deduction_type(
        self,
        *,
        organization_id: UUID,
        code: str,
        name: str,
        calculation_type: str,
        payment_frequency: str,
        pretax: bool,
        enrollment_required: bool,
        cap_amount: Decimal | None,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> DeductionType:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._organization(organization_id)
        if calculation_type not in {"fixed", "percentage"}:
            raise ValueError("deduction calculation type must be fixed or percentage")
        if payment_frequency not in {"monthly", "annual", "one_time"}:
            raise ValueError("unsupported deduction payment frequency")
        item = DeductionType(
            organization_id=organization_id,
            code=code.strip(),
            name=name.strip(),
            calculation_type=calculation_type,
            payment_frequency=payment_frequency,
            pretax=pretax,
            enrollment_required=enrollment_required,
            cap_amount=money(cap_amount) if cap_amount is not None else None,
        )
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.deduction_type.created",
            object_type="deduction_type",
            object_id=item.id,
            after={"code": item.code, "pretax": pretax},
        )
        return item

    def create_compensation_profile(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        base_salary: Decimal,
        tax_category: str,
        overtime_eligible: bool,
        standard_monthly_minutes: int,
        starts_on: date,
        ends_on: date | None,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> EmployeeCompensationProfile:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._employee(organization_id, employee_id)
        if ends_on is not None and ends_on < starts_on:
            raise ValueError("compensation profile end must follow its start")
        if standard_monthly_minutes <= 0:
            raise ValueError("standard monthly minutes must be positive")
        end = ends_on or date.max
        overlap = self.session.scalar(
            select(EmployeeCompensationProfile.id).where(
                EmployeeCompensationProfile.employee_id == employee_id,
                EmployeeCompensationProfile.active.is_(True),
                EmployeeCompensationProfile.starts_on <= end,
                or_(
                    EmployeeCompensationProfile.ends_on.is_(None),
                    EmployeeCompensationProfile.ends_on >= starts_on,
                ),
            )
        )
        if overlap:
            raise ValueError("employee compensation profiles cannot overlap")
        item = EmployeeCompensationProfile(
            organization_id=organization_id,
            employee_id=employee_id,
            base_salary=money(base_salary),
            tax_category=tax_category.strip(),
            overtime_eligible=overtime_eligible,
            standard_monthly_minutes=standard_monthly_minutes,
            starts_on=starts_on,
            ends_on=ends_on,
            created_by=actor_user_id,
        )
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.compensation.created",
            object_type="employee_compensation_profile",
            object_id=item.id,
            after={
                "employee_id": str(employee_id),
                "base_salary": str(item.base_salary),
                "tax_category": item.tax_category,
            },
        )
        return item

    def add_compensation_component(
        self,
        *,
        organization_id: UUID,
        compensation_profile_id: UUID,
        component_type: str,
        catalog_id: UUID,
        value: Decimal,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> EmployeeCompensationComponent:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        profile = self.session.get(EmployeeCompensationProfile, compensation_profile_id)
        if profile is None or profile.organization_id != organization_id:
            raise LookupError("compensation profile not found")
        if component_type == "earning":
            catalog = self.session.get(EarningHead, catalog_id)
            if catalog is None or catalog.organization_id != organization_id or not catalog.active:
                raise LookupError("earning head not found")
            earning_id, deduction_id = catalog.id, None
        elif component_type == "deduction":
            catalog = self.session.get(DeductionType, catalog_id)
            if catalog is None or catalog.organization_id != organization_id or not catalog.active:
                raise LookupError("deduction type not found")
            earning_id, deduction_id = None, catalog.id
        else:
            raise ValueError("component type must be earning or deduction")
        item = EmployeeCompensationComponent(
            compensation_profile_id=profile.id,
            component_type=component_type,
            earning_head_id=earning_id,
            deduction_type_id=deduction_id,
            value=Decimal(str(value)),
        )
        if item.value < 0:
            raise ValueError("compensation component value cannot be negative")
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.compensation.component_added",
            object_type="employee_compensation_component",
            object_id=item.id,
            after={"component_type": component_type, "value": str(item.value)},
        )
        return item

    def create_holiday_overtime_rule(
        self,
        *,
        organization_id: UUID,
        code: str,
        name: str,
        scope_type: str,
        employee_id: UUID | None,
        multiplier: Decimal,
        starts_on: date,
        ends_on: date | None,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> HolidayOvertimeRule:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._organization(organization_id)
        if scope_type not in {"organization", "employee"}:
            raise ValueError("holiday overtime scope must be organization or employee")
        if scope_type == "employee":
            if employee_id is None:
                raise ValueError("employee-scoped overtime rule requires an employee")
            self._employee(organization_id, employee_id)
        elif employee_id is not None:
            raise ValueError("organization overtime rule cannot name an employee")
        if Decimal(str(multiplier)) < 1:
            raise ValueError("holiday overtime multiplier cannot be below 1")
        item = HolidayOvertimeRule(
            organization_id=organization_id,
            code=code.strip(),
            name=name.strip(),
            scope_type=scope_type,
            employee_id=employee_id,
            multiplier=Decimal(str(multiplier)),
            starts_on=starts_on,
            ends_on=ends_on,
        )
        self.session.add(item)
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.holiday_overtime_rule.created",
            object_type="holiday_overtime_rule",
            object_id=item.id,
            after={"scope_type": scope_type, "multiplier": str(item.multiplier)},
        )
        return item

    def create_tax_slab_set(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        taxpayer_category: str,
        version: str,
        standard_deduction: Decimal,
        slabs: Iterable[tuple[Decimal, Decimal | None, Decimal]],
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> TaxSlabSet:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        fiscal_year = self.session.get(FiscalYear, fiscal_year_id)
        if fiscal_year is None or fiscal_year.organization_id != organization_id:
            raise LookupError("fiscal year not found")
        item = TaxSlabSet(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            taxpayer_category=taxpayer_category.strip(),
            version=version.strip(),
            standard_deduction=money(standard_deduction),
            created_by=actor_user_id,
        )
        self.session.add(item)
        self.session.flush()
        previous_upper: Decimal | None = Decimal("0")
        rows = list(slabs)
        if not rows:
            raise ValueError("tax slab set requires at least one slab")
        for sequence, (lower, upper, rate) in enumerate(rows, start=1):
            lower_value = money(lower)
            upper_value = money(upper) if upper is not None else None
            rate_value = Decimal(str(rate))
            if rate_value < 0 or rate_value > 1:
                raise ValueError("tax slab rate must be between 0 and 1")
            if previous_upper is None or lower_value != previous_upper:
                raise ValueError("tax slabs must be contiguous and start at zero")
            if upper_value is not None and upper_value <= lower_value:
                raise ValueError("tax slab upper bound must exceed lower bound")
            if upper_value is None and sequence != len(rows):
                raise ValueError("only the final tax slab may be open-ended")
            self.session.add(
                TaxSlab(
                    tax_slab_set_id=item.id,
                    sequence=sequence,
                    lower_bound=lower_value,
                    upper_bound=upper_value,
                    rate=rate_value,
                )
            )
            previous_upper = upper_value
        if previous_upper is not None:
            raise ValueError("final tax slab must be open-ended")
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.tax_policy.created",
            object_type="tax_slab_set",
            object_id=item.id,
            after={
                "fiscal_year_id": str(fiscal_year_id),
                "taxpayer_category": item.taxpayer_category,
                "version": item.version,
            },
        )
        return item

    def confirm_tax_slab_set(
        self,
        *,
        organization_id: UUID,
        tax_slab_set_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> TaxSlabSet:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        item = self.session.get(TaxSlabSet, tax_slab_set_id)
        if item is None or item.organization_id != organization_id:
            raise LookupError("tax slab set not found")
        if item.status != "draft":
            raise ValueError("only draft tax policies can be confirmed")
        if item.created_by == actor_user_id:
            raise ValueError("tax policy confirmation requires independent approval")
        item.status = "confirmed"
        item.confirmed_by = actor_user_id
        item.confirmed_at = utc_now()
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.tax_policy.confirmed",
            object_type="tax_slab_set",
            object_id=item.id,
            before={"status": "draft"},
            after={"status": "confirmed"},
        )
        return item

    @staticmethod
    def progressive_tax(
        taxable_income: Decimal,
        slab_set: TaxSlabSet,
        slabs: Iterable[TaxSlab],
    ) -> Decimal:
        taxable = max(Decimal("0"), money(taxable_income) - money(slab_set.standard_deduction))
        total = Decimal("0")
        for slab in sorted(slabs, key=lambda item: item.sequence):
            if taxable <= slab.lower_bound:
                break
            top = taxable if slab.upper_bound is None else min(taxable, slab.upper_bound)
            width = max(Decimal("0"), top - slab.lower_bound)
            total += width * slab.rate
        return total.quantize(MONEY, rounding=ROUND_HALF_UP)

    def create_period(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        code: str,
        label: str,
        starts_on: date,
        ends_on: date,
        attendance_calculation_version: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollPeriod:
        fiscal_year = self.session.get(FiscalYear, fiscal_year_id)
        if fiscal_year is None or fiscal_year.organization_id != organization_id:
            raise LookupError("fiscal year not found")
        if fiscal_year.status != "active":
            raise ValueError("payroll period requires an active fiscal year")
        if starts_on < fiscal_year.starts_on or ends_on > fiscal_year.ends_on:
            raise ValueError("payroll period must be contained by its fiscal year")
        period = self.lifecycle.create_period(
            organization_id=organization_id,
            code=code,
            label=label,
            starts_on=starts_on,
            ends_on=ends_on,
            attendance_calculation_version=attendance_calculation_version,
            actor_user_id=actor_user_id,
            grants=grants,
        )
        self.session.add(PayrollPeriodContext(period_id=period.id, fiscal_year_id=fiscal_year.id))
        self.session.flush()
        return period

    def prepare_attendance_review(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        employee_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollAttendanceReview:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        period = self.lifecycle._period(organization_id, period_id)
        employee = self._employee(organization_id, employee_id)
        records = list(
            self.session.execute(
                select(AttendanceRecord, AttendanceRecordDetail)
                .join(
                    AttendanceRecordDetail,
                    AttendanceRecordDetail.attendance_record_id == AttendanceRecord.id,
                )
                .where(
                    AttendanceRecord.organization_id == organization_id,
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.work_date >= period.starts_on,
                    AttendanceRecord.work_date <= period.ends_on,
                )
                .order_by(AttendanceRecord.work_date)
            ).all()
        )
        if not records:
            raise ValueError("attendance must be calculated before payroll review")
        mismatched = [
            record.work_date.isoformat()
            for record, _detail in records
            if record.calculation_version != period.attendance_calculation_version
        ]
        if mismatched:
            raise ValueError("attendance calculation version does not match payroll period")
        statuses: dict[str, int] = {}
        worked_minutes = 0
        regular_ot = 0
        holiday_ot = 0
        fingerprints: list[str] = []
        for record, detail in records:
            statuses[detail.day_status] = statuses.get(detail.day_status, 0) + 1
            worked_minutes += record.worked_minutes
            regular_ot += detail.regular_overtime_minutes
            holiday_ot += detail.holiday_overtime_minutes
            fingerprints.append(detail.input_fingerprint)
        snapshot = {
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "period_id": str(period.id),
            "period_start": period.starts_on.isoformat(),
            "period_end": period.ends_on.isoformat(),
            "calculation_version": period.attendance_calculation_version,
            "record_count": len(records),
            "statuses": statuses,
            "worked_minutes": worked_minutes,
            "regular_overtime_minutes": regular_ot,
            "holiday_overtime_minutes": holiday_ot,
            "input_fingerprints": fingerprints,
        }
        item = self.session.scalar(
            select(PayrollAttendanceReview).where(
                PayrollAttendanceReview.period_id == period.id,
                PayrollAttendanceReview.employee_id == employee.id,
            )
        )
        if item is None:
            item = PayrollAttendanceReview(
                organization_id=organization_id,
                period_id=period.id,
                employee_id=employee.id,
                attendance_snapshot=redact_audit_payload(snapshot),
            )
            self.session.add(item)
        elif item.status == "approved":
            raise ValueError("approved payroll attendance review is immutable")
        else:
            item.attendance_snapshot = redact_audit_payload(snapshot)
            item.status = "pending"
            item.reviewed_by = None
            item.reviewed_at = None
            item.review_note = None
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.attendance_review.prepared",
            object_type="payroll_attendance_review",
            object_id=item.id,
            after={"employee_id": str(employee_id), "record_count": len(records)},
        )
        return item

    def decide_attendance_review(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        approve: bool,
        note: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollAttendanceReview:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        item = self.session.get(PayrollAttendanceReview, review_id)
        if item is None or item.organization_id != organization_id:
            raise LookupError("payroll attendance review not found")
        if item.status != "pending":
            raise ValueError("only pending attendance reviews can be decided")
        item.status = "approved" if approve else "rejected"
        item.reviewed_by = actor_user_id
        item.reviewed_at = utc_now()
        item.review_note = note.strip() or None
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=f"payroll.attendance_review.{item.status}",
            object_type="payroll_attendance_review",
            object_id=item.id,
            after={"status": item.status},
        )
        return item

    def _compensation(
        self,
        organization_id: UUID,
        employee_id: UUID,
        target: date,
    ) -> EmployeeCompensationProfile:
        item = self.session.scalar(
            select(EmployeeCompensationProfile)
            .where(
                EmployeeCompensationProfile.organization_id == organization_id,
                EmployeeCompensationProfile.employee_id == employee_id,
                EmployeeCompensationProfile.active.is_(True),
                EmployeeCompensationProfile.starts_on <= target,
                or_(
                    EmployeeCompensationProfile.ends_on.is_(None),
                    EmployeeCompensationProfile.ends_on >= target,
                ),
            )
            .order_by(EmployeeCompensationProfile.starts_on.desc())
            .limit(1)
        )
        if item is None:
            raise ValueError("employee has no active compensation profile")
        return item

    def _holiday_ot_rule(
        self,
        organization_id: UUID,
        employee_id: UUID,
        target: date,
    ) -> HolidayOvertimeRule | None:
        rows = list(
            self.session.scalars(
                select(HolidayOvertimeRule)
                .where(
                    HolidayOvertimeRule.organization_id == organization_id,
                    HolidayOvertimeRule.active.is_(True),
                    HolidayOvertimeRule.starts_on <= target,
                    or_(
                        HolidayOvertimeRule.ends_on.is_(None),
                        HolidayOvertimeRule.ends_on >= target,
                    ),
                    or_(
                        HolidayOvertimeRule.employee_id == employee_id,
                        and_(
                            HolidayOvertimeRule.scope_type == "organization",
                            HolidayOvertimeRule.employee_id.is_(None),
                        ),
                    ),
                )
                .order_by(HolidayOvertimeRule.starts_on.desc())
            )
        )
        for row in rows:
            if row.scope_type == "employee":
                return row
        return rows[0] if rows else None

    def _confirmed_tax_set(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        tax_category: str,
    ) -> tuple[TaxSlabSet, list[TaxSlab]]:
        item = self.session.scalar(
            select(TaxSlabSet)
            .where(
                TaxSlabSet.organization_id == organization_id,
                TaxSlabSet.fiscal_year_id == fiscal_year_id,
                TaxSlabSet.taxpayer_category == tax_category,
                TaxSlabSet.status == "confirmed",
            )
            .order_by(TaxSlabSet.confirmed_at.desc())
            .limit(1)
        )
        if item is None:
            raise ValueError("confirmed tax policy is required before payroll generation")
        slabs = list(
            self.session.scalars(
                select(TaxSlab)
                .where(TaxSlab.tax_slab_set_id == item.id)
                .order_by(TaxSlab.sequence)
            )
        )
        return item, slabs

    @staticmethod
    def _component_amount(
        *,
        base_salary: Decimal,
        calculation_type: str,
        value: Decimal,
        cap_amount: Decimal | None = None,
    ) -> Decimal:
        amount = value if calculation_type == "fixed" else base_salary * value / PERCENT
        result = money(amount)
        if cap_amount is not None:
            result = min(result, money(cap_amount))
        return result

    def preview_employee(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        employee_id: UUID,
    ) -> dict:
        period = self.lifecycle._period(organization_id, period_id)
        context = self.session.get(PayrollPeriodContext, period.id)
        if context is None:
            raise ValueError("payroll period is not linked to a fiscal year")
        fiscal_year = self.session.get(FiscalYear, context.fiscal_year_id)
        if fiscal_year is None or fiscal_year.status != "active":
            raise ValueError("payroll generation requires an active fiscal year")
        review = self.session.scalar(
            select(PayrollAttendanceReview).where(
                PayrollAttendanceReview.period_id == period.id,
                PayrollAttendanceReview.employee_id == employee_id,
                PayrollAttendanceReview.status == "approved",
            )
        )
        if review is None:
            raise ValueError("approved attendance review is required before payroll generation")
        employee = self._employee(organization_id, employee_id)
        profile = self._compensation(organization_id, employee_id, period.ends_on)
        tax_set, slabs = self._confirmed_tax_set(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year.id,
            tax_category=profile.tax_category,
        )
        components = list(
            self.session.scalars(
                select(EmployeeCompensationComponent).where(
                    EmployeeCompensationComponent.compensation_profile_id == profile.id,
                    EmployeeCompensationComponent.active.is_(True),
                )
            )
        )
        earnings: list[dict] = []
        deductions: list[dict] = []
        taxable_earnings = money(profile.base_salary)
        gross = money(profile.base_salary)
        pretax_deductions = Decimal("0")
        total_deductions = Decimal("0")
        for component in components:
            if component.component_type == "earning":
                head = self.session.get(EarningHead, component.earning_head_id)
                if head is None or not head.active:
                    raise ValueError("compensation references an inactive earning head")
                amount = self._component_amount(
                    base_salary=profile.base_salary,
                    calculation_type=head.calculation_type,
                    value=component.value,
                )
                earnings.append({"code": head.code, "name": head.name, "amount": str(amount)})
                gross += amount
                if head.taxable:
                    taxable_earnings += amount
            else:
                deduction = self.session.get(DeductionType, component.deduction_type_id)
                if deduction is None or not deduction.active:
                    raise ValueError("compensation references an inactive deduction type")
                amount = self._component_amount(
                    base_salary=profile.base_salary,
                    calculation_type=deduction.calculation_type,
                    value=component.value,
                    cap_amount=deduction.cap_amount,
                )
                deductions.append(
                    {
                        "code": deduction.code,
                        "name": deduction.name,
                        "amount": str(amount),
                        "pretax": deduction.pretax,
                    }
                )
                total_deductions += amount
                if deduction.pretax:
                    pretax_deductions += amount
        holiday_ot_minutes = int(review.attendance_snapshot.get("holiday_overtime_minutes", 0))
        ot_rule = self._holiday_ot_rule(organization_id, employee_id, period.ends_on)
        holiday_ot = Decimal("0")
        if profile.overtime_eligible and holiday_ot_minutes > 0 and ot_rule is not None:
            minute_rate = profile.base_salary / Decimal(profile.standard_monthly_minutes)
            holiday_ot = money(minute_rate * Decimal(holiday_ot_minutes) * ot_rule.multiplier)
            earnings.append(
                {
                    "code": "HOLIDAY_OT",
                    "name": ot_rule.name,
                    "amount": str(holiday_ot),
                    "minutes": holiday_ot_minutes,
                    "multiplier": str(ot_rule.multiplier),
                }
            )
            gross += holiday_ot
            taxable_earnings += holiday_ot
        period_taxable = max(Decimal("0"), taxable_earnings - pretax_deductions)
        projected_annual_taxable = money(period_taxable * DEFAULT_ANNUAL_PERIODS)
        projected_annual_tax = self.progressive_tax(projected_annual_taxable, tax_set, slabs)
        period_tax = money(projected_annual_tax / DEFAULT_ANNUAL_PERIODS)
        if total_deductions + period_tax > gross:
            raise ValueError("deductions and tax exceed gross pay")
        net = money(gross - total_deductions - period_tax)
        return {
            "employee": {
                "id": str(employee.id),
                "employee_code": employee.employee_code,
                "display_name": employee.display_name,
            },
            "fiscal_year": {
                "id": str(fiscal_year.id),
                "code": fiscal_year.code,
                "bs_start_year": fiscal_year.bs_start_year,
                "bs_end_year": fiscal_year.bs_end_year,
            },
            "compensation": {
                "profile_id": str(profile.id),
                "base_salary": str(money(profile.base_salary)),
                "tax_category": profile.tax_category,
                "standard_monthly_minutes": profile.standard_monthly_minutes,
            },
            "attendance": review.attendance_snapshot,
            "earnings": earnings,
            "deductions": deductions,
            "tax_policy": {
                "id": str(tax_set.id),
                "version": tax_set.version,
                "category": tax_set.taxpayer_category,
                "standard_deduction": str(tax_set.standard_deduction),
                "slabs": [
                    {
                        "sequence": slab.sequence,
                        "lower_bound": str(slab.lower_bound),
                        "upper_bound": (
                            str(slab.upper_bound)
                            if slab.upper_bound is not None
                            else None
                        ),
                        "rate": str(slab.rate),
                    }
                    for slab in slabs
                ],
            },
            "holiday_overtime_rule": (
                {
                    "id": str(ot_rule.id),
                    "code": ot_rule.code,
                    "multiplier": str(ot_rule.multiplier),
                }
                if ot_rule is not None
                else None
            ),
            "gross": str(money(gross)),
            "deduction_total": str(money(total_deductions)),
            "taxable_period_income": str(money(period_taxable)),
            "projected_annual_taxable_income": str(projected_annual_taxable),
            "projected_annual_tax": str(projected_annual_tax),
            "tax": str(period_tax),
            "net": str(net),
        }

    def generate_run(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        employee_ids: Iterable[UUID],
        calculation_version: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        period = self.lifecycle._period(organization_id, period_id)
        if period.status != "locked":
            raise ValueError("payroll generation requires a locked payroll period")
        previews = [
            self.preview_employee(
                organization_id=organization_id,
                period_id=period_id,
                employee_id=employee_id,
            )
            for employee_id in employee_ids
        ]
        if not previews:
            raise ValueError("payroll generation requires at least one employee")
        policy_snapshot = {
            "engine": calculation_version,
            "fiscal_year": previews[0]["fiscal_year"],
            "tax_policy_ids": sorted({item["tax_policy"]["id"] for item in previews}),
            "attendance_calculation_version": period.attendance_calculation_version,
        }
        run = self.lifecycle.create_run(
            organization_id=organization_id,
            period_id=period.id,
            calculation_version=calculation_version,
            policy_snapshot=policy_snapshot,
            actor_user_id=actor_user_id,
            grants=grants,
        )
        for preview in previews:
            employee_id = UUID(preview["employee"]["id"])
            self.lifecycle.add_line(
                organization_id=organization_id,
                run_id=run.id,
                employee_id=employee_id,
                gross_amount=preview["gross"],
                deduction_amount=preview["deduction_total"],
                tax_amount=preview["tax"],
                employee_snapshot=preview["employee"],
                attendance_snapshot=preview["attendance"],
                earnings_snapshot={
                    "compensation": preview["compensation"],
                    "items": preview["earnings"],
                    "holiday_overtime_rule": preview["holiday_overtime_rule"],
                },
                deductions_snapshot={
                    "items": preview["deductions"],
                    "tax_policy": preview["tax_policy"],
                },
                explanation={
                    "gross": preview["gross"],
                    "deduction_total": preview["deduction_total"],
                    "taxable_period_income": preview["taxable_period_income"],
                    "projected_annual_taxable_income": preview[
                        "projected_annual_taxable_income"
                    ],
                    "projected_annual_tax": preview["projected_annual_tax"],
                    "tax": preview["tax"],
                    "net": preview["net"],
                    "formula": "gross - deductions - tax",
                },
                actor_user_id=actor_user_id,
                grants=grants,
            )
        return run

    def add_adjustment(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        employee_id: UUID,
        adjustment_type: str,
        amount: Decimal,
        reason: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollAdjustment:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        run = self.lifecycle._run(organization_id, run_id)
        if run.status != "draft":
            raise ValueError("payroll adjustments can only change a draft run")
        if adjustment_type not in {"earning", "deduction"}:
            raise ValueError("adjustment type must be earning or deduction")
        line = self.session.scalar(
            select(PayrollLine).where(
                PayrollLine.run_id == run.id,
                PayrollLine.employee_id == employee_id,
            )
        )
        if line is None:
            raise LookupError("payroll line not found")
        value = money(amount)
        if value <= 0:
            raise ValueError("payroll adjustment must be positive")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("payroll adjustment reason cannot be blank")
        item = PayrollAdjustment(
            organization_id=organization_id,
            run_id=run.id,
            employee_id=employee_id,
            adjustment_type=adjustment_type,
            amount=value,
            reason=normalized_reason,
            created_by=actor_user_id,
        )
        self.session.add(item)
        if adjustment_type == "earning":
            line.gross_amount = money(line.gross_amount + value)
        else:
            line.deduction_amount = money(line.deduction_amount + value)
        if line.deduction_amount + line.tax_amount > line.gross_amount:
            raise ValueError("adjustment would make deductions and tax exceed gross pay")
        line.net_amount = money(line.gross_amount - line.deduction_amount - line.tax_amount)
        line.explanation = {
            **line.explanation,
            "adjusted_net": str(line.net_amount),
            "adjustment_id": str(item.id),
            "adjustment_type": adjustment_type,
            "adjustment_amount": str(value),
            "adjustment_reason": normalized_reason,
        }
        self.session.flush()
        self._audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="payroll.adjustment.added",
            object_type="payroll_adjustment",
            object_id=item.id,
            after={
                "run_id": str(run.id),
                "employee_id": str(employee_id),
                "type": adjustment_type,
                "amount": str(value),
            },
            reason=normalized_reason,
        )
        return item

    def tax_projection(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        employee_id: UUID,
        projected_taxable_income: Decimal,
    ) -> dict[str, str]:
        profile = self._compensation(organization_id, employee_id, date.today())
        slab_set, slabs = self._confirmed_tax_set(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            tax_category=profile.tax_category,
        )
        taxable = money(projected_taxable_income)
        tax = self.progressive_tax(taxable, slab_set, slabs)
        return {
            "taxpayer_category": profile.tax_category,
            "tax_policy_version": slab_set.version,
            "projected_taxable_income": str(taxable),
            "projected_tax": str(tax),
        }

    def posted_lines(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None = None,
        fiscal_year_id: UUID | None = None,
    ) -> list[tuple[PayrollLine, PayrollRun, PayrollPeriod]]:
        query = (
            select(PayrollLine, PayrollRun, PayrollPeriod)
            .join(PayrollRun, PayrollRun.id == PayrollLine.run_id)
            .join(PayrollPeriod, PayrollPeriod.id == PayrollRun.period_id)
            .where(
                PayrollRun.organization_id == organization_id,
                PayrollRun.status.in_(("posted", "reversed")),
            )
        )
        if employee_id is not None:
            query = query.where(PayrollLine.employee_id == employee_id)
        if fiscal_year_id is not None:
            query = query.join(
                PayrollPeriodContext,
                PayrollPeriodContext.period_id == PayrollPeriod.id,
            ).where(PayrollPeriodContext.fiscal_year_id == fiscal_year_id)
        ordered = query.order_by(PayrollPeriod.starts_on, PayrollLine.id)
        return list(self.session.execute(ordered).all())

    def annual_summary(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        employee_id: UUID | None = None,
    ) -> list[dict[str, str]]:
        totals: dict[UUID, dict[str, Decimal]] = {}
        names: dict[UUID, tuple[str, str]] = {}
        for line, _run, _period in self.posted_lines(
            organization_id=organization_id,
            employee_id=employee_id,
            fiscal_year_id=fiscal_year_id,
        ):
            factor = Decimal("-1") if line.direction == "reversal" else Decimal("1")
            bucket = totals.setdefault(
                line.employee_id,
                {
                    "gross": Decimal("0"),
                    "deductions": Decimal("0"),
                    "tax": Decimal("0"),
                    "net": Decimal("0"),
                },
            )
            bucket["gross"] += factor * line.gross_amount
            bucket["deductions"] += factor * line.deduction_amount
            bucket["tax"] += factor * line.tax_amount
            bucket["net"] += factor * line.net_amount
            employee = self.session.get(Employee, line.employee_id)
            if employee is not None:
                names[line.employee_id] = (employee.employee_code, employee.display_name)
        return [
            {
                "employee_id": str(employee_id_value),
                "employee_code": names.get(employee_id_value, ("", ""))[0],
                "display_name": names.get(employee_id_value, ("", ""))[1],
                "gross": str(money(values["gross"])),
                "deductions": str(money(values["deductions"])),
                "tax": str(money(values["tax"])),
                "net": str(money(values["net"])),
            }
            for employee_id_value, values in sorted(
                totals.items(),
                key=lambda item: names.get(item[0], (str(item[0]), ""))[0],
            )
        ]

    def annual_summary_xlsx(
        self,
        *,
        organization_id: UUID,
        fiscal_year_id: UUID,
        employee_id: UUID | None = None,
    ) -> bytes:
        rows = self.annual_summary(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            employee_id=employee_id,
        )
        return workbook_bytes(
            title="HajiriFlow annual payroll summary",
            headers=("Employee code", "Employee", "Gross", "Deductions", "Tax", "Net"),
            rows=(
                (
                    row["employee_code"],
                    row["display_name"],
                    row["gross"],
                    row["deductions"],
                    row["tax"],
                    row["net"],
                )
                for row in rows
            ),
            metadata=(("Fiscal year ID", fiscal_year_id),),
        )

    def payslip_payload(
        self,
        *,
        organization_id: UUID,
        line_id: UUID,
        employee_id: UUID | None = None,
    ) -> dict:
        line = self.session.get(PayrollLine, line_id)
        if line is None:
            raise LookupError("payslip not found")
        run = self.lifecycle._run(organization_id, line.run_id)
        if run.status not in {"posted", "reversed"}:
            raise ValueError("payslips are available only for posted payroll")
        if employee_id is not None and line.employee_id != employee_id:
            raise LookupError("payslip not found")
        period = self.session.get(PayrollPeriod, run.period_id)
        if period is None:
            raise LookupError("payroll period not found")
        return {
            "line_id": str(line.id),
            "run_id": str(run.id),
            "period": {
                "code": period.code,
                "label": period.label,
                "starts_on": period.starts_on.isoformat(),
                "ends_on": period.ends_on.isoformat(),
            },
            "employee": line.employee_snapshot,
            "attendance": line.attendance_snapshot,
            "earnings": line.earnings_snapshot,
            "deductions": line.deductions_snapshot,
            "gross": str(line.gross_amount),
            "deduction_total": str(line.deduction_amount),
            "tax": str(line.tax_amount),
            "net": str(line.net_amount),
            "currency": line.currency,
            "direction": line.direction,
            "explanation": line.explanation,
        }

    def payslip_pdf(
        self,
        *,
        organization_id: UUID,
        line_id: UUID,
        employee_id: UUID | None = None,
    ) -> bytes:
        payload = self.payslip_payload(
            organization_id=organization_id,
            line_id=line_id,
            employee_id=employee_id,
        )
        employee = payload["employee"]
        return pdf_bytes(
            title="HajiriFlow payslip",
            headers=("Gross", "Deductions", "Tax", "Net", "Currency"),
            rows=((
                payload["gross"],
                payload["deduction_total"],
                payload["tax"],
                payload["net"],
                payload["currency"],
            ),),
            metadata=(
                ("Employee", employee.get("display_name", "")),
                ("Employee code", employee.get("employee_code", "")),
                ("Period", payload["period"]["label"]),
                ("Direction", payload["direction"]),
            ),
        )
