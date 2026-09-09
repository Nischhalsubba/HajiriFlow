from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class DeviceIdentityAction(Base):
    __tablename__ = "device_identity_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('push_users', 'migrate_users', 'archive_export', 'archive_restore')",
            name="device_identity_action_valid_type",
        ),
        CheckConstraint(
            "status IN ('preview', 'approved', 'running', 'succeeded', 'partial', 'failed', 'cancelled')",
            name="device_identity_action_valid_status",
        ),
        Index("ix_device_identity_actions_org_created", "organization_id", "created_at"),
        Index("ix_device_identity_actions_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="preview")
    source_device_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_device_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeviceArchive(Base):
    __tablename__ = "device_archives"
    __table_args__ = (
        CheckConstraint("status IN ('ready', 'restored', 'failed')", name="device_archive_valid_status"),
        Index("ix_device_archives_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    manifest_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
