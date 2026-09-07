from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.biometric import (
    BiometricConsentEvent,
    BiometricDeletionRequest,
)
from hajiriflow.db.models.device import DeviceEmployeeMapping, DeviceUser
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import Employee

VALID_CONSENT_DECISIONS = {"granted", "declined", "revoked"}


def utc_now() -> datetime:
    return datetime.now(UTC)


class BiometricPrivacyService:
    """Govern device-side biometric use without ingesting biometric material."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def employee(self, *, organization_id: UUID, employee_id: UUID) -> Employee:
        employee = self.session.scalar(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.organization_id == organization_id,
            )
        )
        if employee is None:
            raise LookupError("employee not found")
        return employee

    def record_consent(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        decision: str,
        policy_version: str,
        purpose: str,
        actor_user_id: UUID | None,
    ) -> BiometricConsentEvent:
        employee = self.employee(
            organization_id=organization_id,
            employee_id=employee_id,
        )
        if decision not in VALID_CONSENT_DECISIONS:
            raise ValueError("unsupported biometric consent decision")
        if not policy_version.strip():
            raise ValueError("biometric policy version is required")
        if not purpose.strip():
            raise ValueError("biometric purpose is required")

        event = BiometricConsentEvent(
            organization_id=organization_id,
            employee_id=employee.id,
            decision=decision,
            policy_version=policy_version.strip(),
            purpose=purpose.strip(),
            recorded_by=actor_user_id,
        )
        self.session.add(event)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=f"biometric.consent.{decision}",
                object_type="employee",
                object_id=str(employee.id),
                after_data={
                    "decision": decision,
                    "policy_version": event.policy_version,
                    "purpose": event.purpose,
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return event

    def latest_consent(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
    ) -> BiometricConsentEvent | None:
        self.employee(organization_id=organization_id, employee_id=employee_id)
        return self.session.scalar(
            select(BiometricConsentEvent)
            .where(
                BiometricConsentEvent.organization_id == organization_id,
                BiometricConsentEvent.employee_id == employee_id,
            )
            .order_by(
                BiometricConsentEvent.occurred_at.desc(),
                BiometricConsentEvent.id.desc(),
            )
            .limit(1)
        )

    def request_deletion(
        self,
        *,
        organization_id: UUID,
        device_user_id: UUID,
        reason: str,
        actor_user_id: UUID | None,
    ) -> BiometricDeletionRequest:
        if not reason.strip():
            raise ValueError("biometric deletion reason is required")
        device_user = self.session.scalar(
            select(DeviceUser).where(
                DeviceUser.id == device_user_id,
                DeviceUser.organization_id == organization_id,
            )
        )
        if device_user is None:
            raise LookupError("device user not found")
        mapping = self.session.scalar(
            select(DeviceEmployeeMapping).where(
                DeviceEmployeeMapping.device_user_id == device_user.id,
                DeviceEmployeeMapping.organization_id == organization_id,
            )
        )
        if mapping is None:
            raise LookupError("device user is not mapped to an employee")
        existing = self.session.scalar(
            select(BiometricDeletionRequest).where(
                BiometricDeletionRequest.organization_id == organization_id,
                BiometricDeletionRequest.device_user_id == device_user.id,
                BiometricDeletionRequest.status == "pending",
            )
        )
        if existing is not None:
            raise ValueError("a biometric deletion request is already pending")

        before = {"mapping_status": mapping.status, "device_user_active": device_user.active}
        mapping.status = "disabled"
        mapping.updated_at = utc_now()
        device_user.active = False
        request = BiometricDeletionRequest(
            organization_id=organization_id,
            employee_id=mapping.employee_id,
            device_user_id=device_user.id,
            status="pending",
            reason=reason.strip(),
            requested_by=actor_user_id,
        )
        self.session.add(request)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="biometric.deletion.request",
                object_type="biometric_deletion_request",
                object_id=str(request.id),
                reason=request.reason,
                before_data=before,
                after_data={
                    "mapping_status": "disabled",
                    "device_user_active": False,
                    "status": "pending",
                },
                context_data={
                    "organization_id": str(organization_id),
                    "employee_id": str(mapping.employee_id),
                    "device_user_id": str(device_user.id),
                },
            )
        )
        return request

    def complete_deletion(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        external_receipt_hash: str,
        actor_user_id: UUID | None,
    ) -> BiometricDeletionRequest:
        request = self._deletion_request(
            organization_id=organization_id,
            request_id=request_id,
        )
        if request.status != "pending":
            raise ValueError("only pending biometric deletion requests can be completed")
        receipt_hash = external_receipt_hash.strip().lower()
        if len(receipt_hash) != 64 or any(ch not in "0123456789abcdef" for ch in receipt_hash):
            raise ValueError("external deletion receipt must be represented by a SHA-256 hash")

        request.status = "completed"
        request.completed_by = actor_user_id
        request.completed_at = utc_now()
        request.external_receipt_hash = receipt_hash
        request.failure_code = None
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="biometric.deletion.complete",
                object_type="biometric_deletion_request",
                object_id=str(request.id),
                before_data={"status": "pending"},
                after_data={
                    "status": "completed",
                    "external_receipt_hash": receipt_hash,
                },
                context_data={
                    "organization_id": str(organization_id),
                    "employee_id": str(request.employee_id),
                    "device_user_id": str(request.device_user_id),
                },
            )
        )
        return request

    def fail_deletion(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        failure_code: str,
        actor_user_id: UUID | None,
    ) -> BiometricDeletionRequest:
        request = self._deletion_request(
            organization_id=organization_id,
            request_id=request_id,
        )
        if request.status != "pending":
            raise ValueError("only pending biometric deletion requests can fail")
        safe_code = failure_code.strip().lower()
        if not safe_code or len(safe_code) > 80 or not all(
            ch.isalnum() or ch in {"_", "-", "."} for ch in safe_code
        ):
            raise ValueError("failure code must be a short non-sensitive identifier")

        request.status = "failed"
        request.completed_by = actor_user_id
        request.completed_at = utc_now()
        request.failure_code = safe_code
        request.external_receipt_hash = None
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="biometric.deletion.fail",
                object_type="biometric_deletion_request",
                object_id=str(request.id),
                before_data={"status": "pending"},
                after_data={"status": "failed", "failure_code": safe_code},
                context_data={
                    "organization_id": str(organization_id),
                    "employee_id": str(request.employee_id),
                    "device_user_id": str(request.device_user_id),
                },
            )
        )
        return request

    def pending_deletions(
        self, *, organization_id: UUID
    ) -> list[BiometricDeletionRequest]:
        return list(
            self.session.scalars(
                select(BiometricDeletionRequest)
                .where(
                    BiometricDeletionRequest.organization_id == organization_id,
                    BiometricDeletionRequest.status == "pending",
                )
                .order_by(BiometricDeletionRequest.requested_at.asc())
            ).all()
        )

    def _deletion_request(
        self, *, organization_id: UUID, request_id: UUID
    ) -> BiometricDeletionRequest:
        request = self.session.scalar(
            select(BiometricDeletionRequest).where(
                BiometricDeletionRequest.id == request_id,
                BiometricDeletionRequest.organization_id == organization_id,
            )
        )
        if request is None:
            raise LookupError("biometric deletion request not found")
        return request
