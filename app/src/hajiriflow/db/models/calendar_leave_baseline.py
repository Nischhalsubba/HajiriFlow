from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class LeavePolicyRule(Base):
    __tablename__ = "leave_policy_rules"
    __table_args__ = (
        CheckConstraint(
            "carry_forward_cap IS NULL OR carry_forward_cap >= 0",
            name="leave_policy_rule_nonnegative_carry_cap",
        ),
    )

    leave_policy_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leave_policies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    carry_forward_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    carry_forward_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    color_hex: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#2563EB"
    )
    eligibility_employment_types: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class LeaveAllocationDetail(Base):
    __tablename__ = "leave_allocation_details"
    __table_args__ = (
        CheckConstraint("opening_days >= 0", name="leave_allocation_detail_opening_nonnegative"),
        CheckConstraint("earned_days >= 0", name="leave_allocation_detail_earned_nonnegative"),
        CheckConstraint(
            "source IN ('manual', 'annual')",
            name="leave_allocation_detail_valid_source",
        ),
    )

    leave_allocation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leave_allocations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    opening_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    earned_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class FieldDutyDetail(Base):
    __tablename__ = "field_duty_details"

    field_duty_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("field_duty_requests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(400), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
