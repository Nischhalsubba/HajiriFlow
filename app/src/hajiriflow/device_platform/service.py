import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.device import (
    Device,
    DeviceCredential,
    DeviceEmployeeMapping,
    DevicePullSession,
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import Employee
from hajiriflow.device_platform.adapters import DeviceUserRecord, PunchRecord
from hajiriflow.device_platform.crypto import DeviceSecretCipher

SENSITIVE_EVIDENCE_TERMS = {
    "biometric",
    "face",
    "finger",
    "image",
    "password",
    "photo",
    "secret",
    "template",
    "token",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _assert_safe_metadata(value: Mapping[str, object]) -> None:
    for key in value:
        normalized = key.casefold().replace("-", "_")
        if any(term in normalized for term in SENSITIVE_EVIDENCE_TERMS):
            raise ValueError(f"sensitive device evidence field is not accepted: {key}")


def punch_fingerprint(device_id: UUID, punch: PunchRecord) -> str:
    identity = {
        "device_id": str(device_id),
        "external_event_id": punch.external_event_id,
        "device_user_identifier": punch.device_user_identifier,
        "occurred_at": punch.occurred_at.astimezone(UTC).isoformat(),
        "punch_kind": punch.punch_kind,
        "verification_method": punch.verification_method,
        "evidence": punch.evidence,
    }
    return hashlib.sha256(_canonical_json(identity).encode()).hexdigest()


class DevicePlatformService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def rotate_credential(
        self,
        *,
        device: Device,
        secret: Mapping[str, str],
        cipher: DeviceSecretCipher,
        actor_user_id: UUID | None,
    ) -> DeviceCredential:
        key_id, ciphertext = cipher.encrypt(secret)
        active_credentials = self.session.scalars(
            select(DeviceCredential).where(
                DeviceCredential.device_id == device.id,
                DeviceCredential.retired_at.is_(None),
            )
        ).all()
        latest_version = self.session.scalar(
            select(DeviceCredential.version)
            .where(DeviceCredential.device_id == device.id)
            .order_by(DeviceCredential.version.desc())
            .limit(1)
        )
        now = utc_now()
        for existing in active_credentials:
            existing.retired_at = now

        credential = DeviceCredential(
            organization_id=device.organization_id,
            device_id=device.id,
            version=(latest_version or 0) + 1,
            key_id=key_id,
            ciphertext=ciphertext,
            created_by=actor_user_id,
            created_at=now,
        )
        self.session.add(credential)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="device.credential.rotate",
                object_type="device",
                object_id=str(device.id),
                after_data={"credential_version": credential.version, "key_id": key_id},
                context_data={"organization_id": str(device.organization_id)},
            )
        )
        return credential

    def ingest_punches(
        self,
        *,
        device: Device,
        punches: Iterable[PunchRecord],
        pull_session: DevicePullSession | None = None,
    ) -> tuple[int, int]:
        inserted = 0
        duplicates = 0
        for punch in punches:
            _assert_safe_metadata(punch.evidence)
            if punch.punch_kind not in {"in", "out", "break", "unknown"}:
                raise ValueError(f"unsupported punch kind: {punch.punch_kind}")
            fingerprint = punch_fingerprint(device.id, punch)
            exists = self.session.scalar(
                select(RawPunch.id).where(
                    RawPunch.device_id == device.id,
                    RawPunch.source_fingerprint == fingerprint,
                )
            )
            if exists is not None:
                duplicates += 1
                continue
            self.session.add(
                RawPunch(
                    organization_id=device.organization_id,
                    device_id=device.id,
                    pull_session_id=pull_session.id if pull_session else None,
                    external_event_id=punch.external_event_id,
                    device_user_identifier=punch.device_user_identifier,
                    occurred_at=punch.occurred_at,
                    punch_kind=punch.punch_kind,
                    verification_method=punch.verification_method,
                    source_fingerprint=fingerprint,
                    evidence=dict(punch.evidence),
                )
            )
            self.session.flush()
            inserted += 1
        return inserted, duplicates

    def sync_device_users(
        self,
        *,
        device: Device,
        users: Iterable[DeviceUserRecord],
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        now = utc_now()
        for record in users:
            _assert_safe_metadata(record.metadata)
            source_hash = hashlib.sha256(
                _canonical_json(
                    {
                        "external_user_id": record.external_user_id,
                        "display_name": record.display_name,
                        "privilege": record.privilege,
                        "active": record.active,
                        "template_count": record.template_count,
                        "metadata": record.metadata,
                    }
                ).encode()
            ).hexdigest()
            existing = self.session.scalar(
                select(DeviceUser).where(
                    DeviceUser.device_id == device.id,
                    DeviceUser.external_user_id == record.external_user_id,
                )
            )
            if existing is None:
                self.session.add(
                    DeviceUser(
                        organization_id=device.organization_id,
                        device_id=device.id,
                        external_user_id=record.external_user_id,
                        display_name=record.display_name,
                        privilege=record.privilege,
                        active=record.active,
                        template_count=record.template_count,
                        source_hash=source_hash,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
                created += 1
                continue
            existing.display_name = record.display_name
            existing.privilege = record.privilege
            existing.active = record.active
            existing.template_count = record.template_count
            existing.source_hash = source_hash
            existing.last_seen_at = now
            updated += 1
        self.session.flush()
        return created, updated

    def map_device_user(
        self,
        *,
        device_user: DeviceUser,
        employee: Employee,
        actor_user_id: UUID | None,
    ) -> DeviceEmployeeMapping:
        if device_user.organization_id != employee.organization_id:
            raise ValueError("device user and employee must belong to the same organization")
        existing = self.session.scalar(
            select(DeviceEmployeeMapping).where(
                DeviceEmployeeMapping.device_user_id == device_user.id
            )
        )
        if existing is not None:
            existing.employee_id = employee.id
            existing.status = "active"
            existing.updated_at = utc_now()
            mapping = existing
        else:
            mapping = DeviceEmployeeMapping(
                organization_id=employee.organization_id,
                device_user_id=device_user.id,
                employee_id=employee.id,
                created_by=actor_user_id,
            )
            self.session.add(mapping)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="device.user.map",
                object_type="device_user",
                object_id=str(device_user.id),
                after_data={"employee_id": str(employee.id)},
                context_data={"organization_id": str(employee.organization_id)},
            )
        )
        return mapping
