from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class DeviceRuntimeConfiguration(Base):
    __tablename__ = "device_runtime_configurations"
    __table_args__ = (
        CheckConstraint("timeout_seconds >= 1", name="device_runtime_positive_timeout"),
        CheckConstraint("timeout_seconds <= 120", name="device_runtime_bounded_timeout"),
    )

    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    site: Mapped[str | None] = mapped_column(String(160), nullable=True)
    protocol_preference: Mapped[str] = mapped_column(
        String(40), nullable=False, default="auto"
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_successful_pull_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_diagnostics_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DeviceOperation(Base):
    __tablename__ = "device_operations"
    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('diagnostics', 'immediate_pull', 'historical_pull')",
            name="device_operation_valid_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')",
            name="device_operation_valid_status",
        ),
        CheckConstraint(
            "window_end IS NULL OR window_start IS NOT NULL",
            name="device_operation_window_start_required",
        ),
        CheckConstraint(
            "window_end IS NULL OR window_end >= window_start",
            name="device_operation_valid_window",
        ),
        Index("ix_device_operations_device_created", "device_id", "created_at"),
        Index("ix_device_operations_status_created", "status", "created_at"),
        Index("ix_device_operations_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
