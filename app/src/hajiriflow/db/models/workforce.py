from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="company_profile_valid_status",
        ),
        Index("ix_company_profiles_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Kathmandu"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class OrganizationNode(Base):
    __tablename__ = "organization_nodes"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('directorate', 'department', 'section', 'unit')",
            name="organization_node_valid_type",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="organization_node_valid_status",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="organization_node_not_own_parent",
        ),
        UniqueConstraint(
            "organization_id", "code", name="uq_organization_node_code"
        ),
        Index("ix_organization_nodes_org_parent", "organization_id", "parent_id"),
        Index(
            "ix_organization_nodes_org_type_status",
            "organization_id",
            "node_type",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organization_nodes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    node_type: Mapped[str] = mapped_column(String(24), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'terminated')",
            name="employee_valid_status",
        ),
        CheckConstraint(
            "left_on IS NULL OR left_on >= joined_on",
            name="employee_valid_dates",
        ),
        UniqueConstraint(
            "organization_id", "employee_code", name="uq_employee_org_code"
        ),
        Index("ix_employees_org_status", "organization_id", "status"),
        Index("ix_employees_org_name", "organization_id", "display_name"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    joined_on: Mapped[date] = mapped_column(Date, nullable=False)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EmployeeOrganizationAssignment(Base):
    __tablename__ = "employee_organization_assignments"
    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="employee_org_assignment_valid_dates",
        ),
        Index(
            "ix_employee_org_assignments_employee_dates",
            "employee_id",
            "starts_on",
            "ends_on",
        ),
        Index(
            "ix_employee_org_assignments_node_dates",
            "organization_node_id",
            "starts_on",
            "ends_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organization_nodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_shift_org_code"),
        CheckConstraint("break_minutes >= 0", name="shift_nonnegative_break"),
        CheckConstraint("grace_minutes >= 0", name="shift_nonnegative_grace"),
        Index("ix_shifts_org_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grace_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (
        CheckConstraint(
            "(employee_id IS NOT NULL AND organization_node_id IS NULL) OR "
            "(employee_id IS NULL AND organization_node_id IS NOT NULL)",
            name="shift_assignment_exactly_one_target",
        ),
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="shift_assignment_valid_dates",
        ),
        Index(
            "ix_shift_assignments_employee_dates",
            "employee_id",
            "starts_on",
            "ends_on",
        ),
        Index(
            "ix_shift_assignments_node_dates",
            "organization_node_id",
            "starts_on",
            "ends_on",
        ),
        Index(
            "ix_shift_assignments_shift_dates",
            "shift_id",
            "starts_on",
            "ends_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    shift_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shifts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=True,
    )
    organization_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organization_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
