from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class CompanyReportProfile(Base):
    """Report/contact metadata kept separate from the legal company record."""

    __tablename__ = "company_report_profiles"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    report_header: Mapped[str | None] = mapped_column(String(240), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EmployeeProfile(Base):
    """Operational HR fields that extend the stable employee identity record."""

    __tablename__ = "employee_profiles"
    __table_args__ = (
        CheckConstraint(
            "employment_type IN ('permanent', 'contract', 'temporary', 'intern', 'consultant')",
            name="employee_profile_valid_employment_type",
        ),
        UniqueConstraint(
            "organization_id", "attendance_id", name="uq_employee_profile_org_attendance_id"
        ),
        UniqueConstraint(
            "organization_id", "hr_employee_number", name="uq_employee_profile_org_hr_number"
        ),
        Index("ix_employee_profiles_org_employment_type", "organization_id", "employment_type"),
        Index("ix_employee_profiles_org_attendance_id", "organization_id", "attendance_id"),
    )

    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    attendance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hr_employee_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    employment_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="permanent"
    )
    designation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payroll_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
