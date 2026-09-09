from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="fiscal_year_valid_dates"),
        CheckConstraint(
            "status IN ('upcoming', 'active', 'closed', 'locked')",
            name="fiscal_year_valid_status",
        ),
        CheckConstraint("bs_start_year >= 2000", name="fiscal_year_valid_bs_start"),
        CheckConstraint("bs_end_year >= bs_start_year", name="fiscal_year_valid_bs_end"),
        UniqueConstraint("organization_id", "code", name="uq_fiscal_year_org_code"),
        Index("ix_fiscal_year_org_status", "organization_id", "status"),
        Index("ix_fiscal_year_org_dates", "organization_id", "starts_on", "ends_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    bs_start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    bs_end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="upcoming")
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    activated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EarningHead(Base):
    __tablename__ = "earning_heads"
    __table_args__ = (
        CheckConstraint(
            "calculation_type IN ('fixed', 'percentage')",
            name="earning_head_valid_calculation_type",
        ),
        CheckConstraint(
            "payment_frequency IN ('monthly', 'annual', 'one_time')",
            name="earning_head_valid_frequency",
        ),
        UniqueConstraint("organization_id", "code", name="uq_earning_head_org_code"),
        Index("ix_earning_head_org_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    calculation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DeductionType(Base):
    __tablename__ = "deduction_types"
    __table_args__ = (
        CheckConstraint(
            "calculation_type IN ('fixed', 'percentage')",
            name="deduction_type_valid_calculation_type",
        ),
        CheckConstraint(
            "payment_frequency IN ('monthly', 'annual', 'one_time')",
            name="deduction_type_valid_frequency",
        ),
        CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="deduction_type_nonnegative_cap",
        ),
        UniqueConstraint("organization_id", "code", name="uq_deduction_type_org_code"),
        Index("ix_deduction_type_org_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    calculation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    pretax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enrollment_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cap_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class HolidayOvertimeRule(Base):
    __tablename__ = "holiday_overtime_rules"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('organization', 'employee')",
            name="holiday_ot_valid_scope",
        ),
        CheckConstraint(
            "(scope_type = 'organization' AND employee_id IS NULL) OR "
            "(scope_type = 'employee' AND employee_id IS NOT NULL)",
            name="holiday_ot_scope_matches_employee",
        ),
        CheckConstraint("multiplier >= 1", name="holiday_ot_valid_multiplier"),
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="holiday_ot_valid_dates",
        ),
        Index("ix_holiday_ot_org_dates", "organization_id", "starts_on", "ends_on"),
        Index("ix_holiday_ot_employee_dates", "employee_id", "starts_on", "ends_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=True,
    )
    multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeCompensationProfile(Base):
    __tablename__ = "employee_compensation_profiles"
    __table_args__ = (
        CheckConstraint("base_salary >= 0", name="comp_profile_nonnegative_salary"),
        CheckConstraint(
            "standard_monthly_minutes > 0",
            name="comp_profile_positive_monthly_minutes",
        ),
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="comp_profile_valid_dates",
        ),
        Index(
            "ix_comp_profile_employee_dates",
            "employee_id",
            "starts_on",
            "ends_on",
        ),
        Index("ix_comp_profile_org_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_salary: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_category: Mapped[str] = mapped_column(String(60), nullable=False, default="resident")
    overtime_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    standard_monthly_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=12480)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EmployeeCompensationComponent(Base):
    __tablename__ = "employee_compensation_components"
    __table_args__ = (
        CheckConstraint(
            "component_type IN ('earning', 'deduction')",
            name="comp_component_valid_type",
        ),
        CheckConstraint("value >= 0", name="comp_component_nonnegative_value"),
        CheckConstraint(
            "(component_type = 'earning' AND earning_head_id IS NOT NULL "
            "AND deduction_type_id IS NULL) OR "
            "(component_type = 'deduction' AND deduction_type_id IS NOT NULL "
            "AND earning_head_id IS NULL)",
            name="comp_component_reference_matches_type",
        ),
        Index("ix_comp_component_profile", "compensation_profile_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    compensation_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employee_compensation_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_type: Mapped[str] = mapped_column(String(20), nullable=False)
    earning_head_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("earning_heads.id", ondelete="RESTRICT"),
        nullable=True,
    )
    deduction_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deduction_types.id", ondelete="RESTRICT"),
        nullable=True,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TaxSlabSet(Base):
    __tablename__ = "tax_slab_sets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed')",
            name="tax_slab_set_valid_status",
        ),
        UniqueConstraint(
            "fiscal_year_id",
            "taxpayer_category",
            "version",
            name="uq_tax_slab_set_fy_category_version",
        ),
        Index(
            "ix_tax_slab_set_org_category_status",
            "organization_id",
            "taxpayer_category",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fiscal_year_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    taxpayer_category: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    standard_deduction: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    confirmed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaxSlab(Base):
    __tablename__ = "tax_slabs"
    __table_args__ = (
        CheckConstraint("lower_bound >= 0", name="tax_slab_nonnegative_lower"),
        CheckConstraint(
            "upper_bound IS NULL OR upper_bound > lower_bound",
            name="tax_slab_valid_bounds",
        ),
        CheckConstraint("rate >= 0 AND rate <= 1", name="tax_slab_valid_rate"),
        UniqueConstraint("tax_slab_set_id", "sequence", name="uq_tax_slab_set_sequence"),
        Index("ix_tax_slab_set_bounds", "tax_slab_set_id", "lower_bound"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tax_slab_set_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tax_slab_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)


class PayrollPeriodContext(Base):
    __tablename__ = "payroll_period_contexts"

    period_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_periods.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fiscal_year_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PayrollAttendanceReview(Base):
    __tablename__ = "payroll_attendance_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="payroll_attendance_review_valid_status",
        ),
        UniqueConstraint(
            "period_id",
            "employee_id",
            name="uq_payroll_attendance_review_period_employee",
        ),
        Index("ix_payroll_attendance_review_status", "period_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attendance_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PayrollAdjustment(Base):
    __tablename__ = "payroll_adjustments"
    __table_args__ = (
        CheckConstraint(
            "adjustment_type IN ('earning', 'deduction')",
            name="payroll_adjustment_valid_type",
        ),
        CheckConstraint("amount > 0", name="payroll_adjustment_positive_amount"),
        Index("ix_payroll_adjustment_run_employee", "run_id", "employee_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
