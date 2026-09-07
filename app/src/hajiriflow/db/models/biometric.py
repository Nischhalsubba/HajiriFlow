from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from hajiriflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class BiometricConsentEvent(Base):
    """Append-only record of employee consent decisions.

    HajiriFlow intentionally stores no biometric templates, images, or scans. These
    events record only the employee decision, the policy version and the declared
    purpose for device-side biometric verification.
    """

    __tablename__ = "biometric_consent_events"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('granted', 'declined', 'revoked')",
            name="biometric_consent_valid_decision",
        ),
        Index(
            "ix_biometric_consent_employee_time",
            "organization_id",
            "employee_id",
            "occurred_at",
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
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


@event.listens_for(BiometricConsentEvent, "before_update")
def _prevent_biometric_consent_update(
    _mapper: object, _connection: object, _target: BiometricConsentEvent
) -> None:
    raise RuntimeError("Biometric consent events are append-only")


@event.listens_for(BiometricConsentEvent, "before_delete")
def _prevent_biometric_consent_delete(
    _mapper: object, _connection: object, _target: BiometricConsentEvent
) -> None:
    raise RuntimeError("Biometric consent events are append-only")


class BiometricDeletionRequest(Base):
    """Tracks deletion of device-side biometric enrollment without storing it."""

    __tablename__ = "biometric_deletion_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="biometric_deletion_valid_status",
        ),
        Index(
            "ix_biometric_deletion_org_status",
            "organization_id",
            "status",
            "requested_at",
        ),
        Index(
            "ix_biometric_deletion_employee",
            "organization_id",
            "employee_id",
            "requested_at",
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
    device_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    external_receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
