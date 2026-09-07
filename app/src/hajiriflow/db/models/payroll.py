from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="payroll_period_valid_dates"),
        CheckConstraint(
            "status IN ('open', 'locked', 'closed')",
            name="payroll_period_valid_status",
        ),
        CheckConstraint(
            "(status = 'open' AND locked_at IS NULL AND locked_by IS NULL) OR "
            "(status IN ('locked', 'closed') AND locked_at IS NOT NULL AND locked_by IS NOT NULL)",
            name="payroll_period_lock_consistency",
        ),
        CheckConstraint(
            "(status <> 'closed' AND closed_at IS NULL AND closed_by IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL AND closed_by IS NOT NULL)",
            name="payroll_period_close_consistency",
        ),
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_payroll_period_org_code",
        ),
        Index(
            "ix_payroll_periods_org_dates",
            "organization_id",
            "starts_on",
            "ends_on",
        ),
        Index("ix_payroll_periods_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    attendance_calculation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    locked_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'posted', "
            "'reversal_pending', 'reversed')",
            name="payroll_run_valid_status",
        ),
        CheckConstraint("sequence >= 1", name="payroll_run_positive_sequence"),
        UniqueConstraint("period_id", "sequence", name="uq_payroll_run_period_sequence"),
        Index("ix_payroll_runs_org_status", "organization_id", "status"),
        Index("ix_payroll_runs_period_status", "period_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_periods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    calculation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reversal_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reversed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversal_of_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reversal_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )


class PayrollLine(Base):
    __tablename__ = "payroll_lines"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('payroll', 'reversal')",
            name="payroll_line_valid_direction",
        ),
        CheckConstraint("gross_amount >= 0", name="payroll_line_nonnegative_gross"),
        CheckConstraint(
            "deduction_amount >= 0",
            name="payroll_line_nonnegative_deduction",
        ),
        CheckConstraint("tax_amount >= 0", name="payroll_line_nonnegative_tax"),
        CheckConstraint("net_amount >= 0", name="payroll_line_nonnegative_net"),
        UniqueConstraint("run_id", "employee_id", name="uq_payroll_line_run_employee"),
        Index("ix_payroll_lines_employee", "employee_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="payroll")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NPR")
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    deduction_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    employee_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    attendance_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    earnings_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    deductions_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False)


class PayrollHistory(Base):
    __tablename__ = "payroll_history"
    __table_args__ = (
        Index("ix_payroll_history_run_time", "run_id", "occurred_at"),
        Index("ix_payroll_history_org_time", "organization_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


@event.listens_for(PayrollHistory, "before_update")
def _prevent_payroll_history_update(
    _mapper: object, _connection: object, _target: PayrollHistory
) -> None:
    raise RuntimeError("Payroll history is immutable")


@event.listens_for(PayrollHistory, "before_delete")
def _prevent_payroll_history_delete(
    _mapper: object, _connection: object, _target: PayrollHistory
) -> None:
    raise RuntimeError("Payroll history is immutable")
