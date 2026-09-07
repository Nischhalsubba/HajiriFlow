from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'error')",
            name="device_valid_status",
        ),
        CheckConstraint(
            "pull_interval_seconds >= 60",
            name="device_minimum_pull_interval",
        ),
        UniqueConstraint("organization_id", "code", name="uq_device_org_code"),
        UniqueConstraint(
            "organization_id", "serial_number", name="uq_device_org_serial"
        ),
        Index("ix_devices_org_status", "organization_id", "status"),
        Index("ix_devices_adapter_status", "adapter_key", "status"),
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
    vendor: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    adapter_key: Mapped[str] = mapped_column(String(120), nullable=False)
    endpoint_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    pull_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DeviceCredential(Base):
    __tablename__ = "device_credentials"
    __table_args__ = (
        CheckConstraint("version >= 1", name="device_credential_positive_version"),
        UniqueConstraint(
            "device_id", "version", name="uq_device_credential_version"
        ),
        Index(
            "ix_device_credentials_device_active",
            "device_id",
            "retired_at",
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
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DevicePullSession(Base):
    __tablename__ = "device_pull_sessions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('scheduled', 'immediate')",
            name="device_pull_session_valid_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'skipped')",
            name="device_pull_session_valid_status",
        ),
        CheckConstraint(
            "attempt_count >= 1", name="device_pull_session_positive_attempts"
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="device_pull_session_valid_times",
        ),
        Index(
            "ix_device_pull_sessions_device_started",
            "device_id",
            "started_at",
        ),
        Index(
            "ix_device_pull_sessions_org_status",
            "organization_id",
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
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cursor_before: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cursor_after: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ingested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RawPunch(Base):
    __tablename__ = "raw_punches"
    __table_args__ = (
        CheckConstraint(
            "punch_kind IN ('in', 'out', 'break', 'unknown')",
            name="raw_punch_valid_kind",
        ),
        UniqueConstraint(
            "device_id", "source_fingerprint", name="uq_raw_punch_device_fingerprint"
        ),
        Index("ix_raw_punches_org_time", "organization_id", "occurred_at"),
        Index("ix_raw_punches_device_time", "device_id", "occurred_at"),
        Index("ix_raw_punches_device_user", "device_id", "device_user_identifier"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pull_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device_pull_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device_user_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    punch_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    verification_method: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


@event.listens_for(RawPunch, "before_update")
def _prevent_raw_punch_update(_mapper: object, _connection: object, _target: RawPunch) -> None:
    raise RuntimeError("Raw punch evidence is immutable")


@event.listens_for(RawPunch, "before_delete")
def _prevent_raw_punch_delete(_mapper: object, _connection: object, _target: RawPunch) -> None:
    raise RuntimeError("Raw punch evidence is immutable")


class DeviceUser(Base):
    __tablename__ = "device_users"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "external_user_id", name="uq_device_user_external_id"
        ),
        Index("ix_device_users_org_device", "organization_id", "device_id"),
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
    external_user_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    privilege: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    template_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DeviceEmployeeMapping(Base):
    __tablename__ = "device_employee_mappings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="device_employee_mapping_valid_status",
        ),
        UniqueConstraint("device_user_id", name="uq_device_employee_mapping_user"),
        Index(
            "ix_device_employee_mappings_employee",
            "organization_id",
            "employee_id",
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
    device_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
