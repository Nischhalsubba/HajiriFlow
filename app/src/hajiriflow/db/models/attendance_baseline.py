from datetime import UTC, date, datetime
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


class AttendancePolicy(Base):
    __tablename__ = "attendance_policies"
    __table_args__ = (
        CheckConstraint(
            "duplicate_window_seconds >= 0 AND duplicate_window_seconds <= 3600",
            name="attendance_policy_duplicate_window_bounds",
        ),
        CheckConstraint(
            "pre_shift_window_minutes >= 0 AND pre_shift_window_minutes <= 1440",
            name="attendance_policy_pre_shift_bounds",
        ),
        CheckConstraint(
            "post_shift_window_minutes >= 0 AND post_shift_window_minutes <= 1440",
            name="attendance_policy_post_shift_bounds",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    duplicate_window_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120
    )
    pre_shift_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=240
    )
    post_shift_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480
    )
    manual_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ManualAttendanceEvent(Base):
    __tablename__ = "manual_attendance_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('in', 'out')",
            name="manual_attendance_event_valid_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked')",
            name="manual_attendance_event_valid_status",
        ),
        UniqueConstraint(
            "import_session_id",
            "import_row_number",
            name="uq_manual_event_import_row",
        ),
        Index(
            "ix_manual_attendance_events_employee_time",
            "employee_id",
            "event_time",
        ),
        Index(
            "ix_manual_attendance_events_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
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
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(12), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decided_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    import_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_import_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    import_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AttendanceImportSession(Base):
    __tablename__ = "attendance_import_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('preview', 'applied', 'rejected')",
            name="attendance_import_session_valid_status",
        ),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 "
            "AND applied_rows >= 0",
            name="attendance_import_session_nonnegative_counts",
        ),
        UniqueConstraint(
            "organization_id",
            "content_sha256",
            name="uq_attendance_import_org_content",
        ),
        Index(
            "ix_attendance_import_sessions_org_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(240), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    strict_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="preview")
    requested_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AttendanceImportRow(Base):
    __tablename__ = "attendance_import_rows"
    __table_args__ = (
        UniqueConstraint("session_id", "row_number", name="uq_attendance_import_row"),
        Index("ix_attendance_import_rows_session_valid", "session_id", "is_valid"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_import_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    applied_event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("manual_attendance_events.id", ondelete="SET NULL"),
        nullable=True,
    )


class AttendanceDayRemark(Base):
    __tablename__ = "attendance_day_remarks"
    __table_args__ = (
        Index(
            "ix_attendance_day_remarks_employee_date",
            "employee_id",
            "work_date",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
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
    remark: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AttendanceRecordDetail(Base):
    __tablename__ = "attendance_record_details"
    __table_args__ = (
        CheckConstraint(
            "day_status IN ('present', 'partial', 'absent', 'leave', 'field_duty', "
            "'holiday', 'weekly_off')",
            name="attendance_record_detail_valid_status",
        ),
        CheckConstraint(
            "planned_minutes >= 0 AND break_minutes >= 0 AND early_arrival_minutes >= 0 "
            "AND early_departure_minutes >= 0 AND late_departure_minutes >= 0 "
            "AND regular_overtime_minutes >= 0 AND holiday_overtime_minutes >= 0 "
            "AND duplicate_event_count >= 0",
            name="attendance_record_detail_nonnegative_metrics",
        ),
        Index("ix_attendance_record_details_status", "day_status"),
    )

    attendance_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day_status: Mapped[str] = mapped_column(String(24), nullable=False)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_arrival_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_departure_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_departure_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    regular_overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    holiday_overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation_trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AttendancePeriodLock(Base):
    __tablename__ = "attendance_period_locks"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="attendance_period_lock_valid_dates"),
        CheckConstraint(
            "status IN ('locked', 'reopened')",
            name="attendance_period_lock_valid_status",
        ),
        Index(
            "ix_attendance_period_locks_org_dates",
            "organization_id",
            "starts_on",
            "ends_on",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    locked_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    reopened_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    reopened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


@event.listens_for(AttendanceDayRemark, "before_update")
def _prevent_remark_update(
    _mapper: object,
    _connection: object,
    _target: AttendanceDayRemark,
) -> None:
    raise RuntimeError("Attendance day remarks are append-only")


@event.listens_for(AttendanceDayRemark, "before_delete")
def _prevent_remark_delete(
    _mapper: object,
    _connection: object,
    _target: AttendanceDayRemark,
) -> None:
    raise RuntimeError("Attendance day remarks are append-only")
