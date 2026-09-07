from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('present', 'absent', 'partial')",
            name="attendance_record_valid_status",
        ),
        CheckConstraint(
            "worked_minutes >= 0 AND late_minutes >= 0 AND source_punch_count >= 0",
            name="attendance_record_nonnegative_metrics",
        ),
        CheckConstraint(
            "check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at",
            name="attendance_record_valid_times",
        ),
        CheckConstraint("source_revision >= 1", name="attendance_record_positive_revision"),
        UniqueConstraint(
            "organization_id",
            "employee_id",
            "work_date",
            name="uq_attendance_record_employee_day",
        ),
        Index(
            "ix_attendance_records_org_date",
            "organization_id",
            "work_date",
        ),
        Index(
            "ix_attendance_records_employee_date",
            "employee_id",
            "work_date",
        ),
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
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_punch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="attendance_correction_valid_status",
        ),
        CheckConstraint(
            "proposed_status IS NULL OR proposed_status IN ('present', 'absent', 'partial')",
            name="attendance_correction_valid_proposed_status",
        ),
        CheckConstraint(
            "proposed_check_out_at IS NULL OR proposed_check_in_at IS NULL OR "
            "proposed_check_out_at >= proposed_check_in_at",
            name="attendance_correction_valid_times",
        ),
        CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL AND decided_by IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL "
            "AND decided_by IS NOT NULL)",
            name="attendance_correction_decision_consistency",
        ),
        Index(
            "ix_attendance_corrections_record_status",
            "attendance_record_id",
            "status",
        ),
        Index(
            "ix_attendance_corrections_org_requested",
            "organization_id",
            "requested_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attendance_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_check_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proposed_check_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proposed_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceHistory(Base):
    __tablename__ = "attendance_history"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('calculated', 'recalculated', 'correction_requested', "
            "'correction_approved', 'correction_rejected')",
            name="attendance_history_valid_event_type",
        ),
        Index(
            "ix_attendance_history_record_time",
            "attendance_record_id",
            "occurred_at",
        ),
        Index(
            "ix_attendance_history_org_time",
            "organization_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attendance_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    correction_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_corrections.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


@event.listens_for(AttendanceHistory, "before_update")
def _prevent_attendance_history_update(
    _mapper: object, _connection: object, _target: AttendanceHistory
) -> None:
    raise RuntimeError("Attendance history is immutable")


@event.listens_for(AttendanceHistory, "before_delete")
def _prevent_attendance_history_delete(
    _mapper: object, _connection: object, _target: AttendanceHistory
) -> None:
    raise RuntimeError("Attendance history is immutable")
