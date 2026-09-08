import base64
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.device import Device, DevicePullSession, DeviceUser
from hajiriflow.db.models.device_baseline import (
    DeviceDiagnosticSnapshot,
    DeviceIdentityArchive,
    DeviceJob,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.device_platform.adapters import DeviceAdapter, DeviceUserRecord
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.pull import DevicePullCoordinator, device_pull_lock
from hajiriflow.device_platform.service import DevicePlatformService

AdapterResolver = Callable[[Device], DeviceAdapter]

JOB_TYPES = {
    "diagnostics",
    "immediate_pull",
    "historical_pull",
    "sync_users",
    "push_user",
    "migrate_user",
    "archive_user",
    "restore_user",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


class DeviceJobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        *,
        device: Device,
        job_type: str,
        payload: dict,
        requested_by: UUID | None,
    ) -> DeviceJob:
        if job_type not in JOB_TYPES:
            raise ValueError("unsupported device job type")
        if device.status != "active" and job_type not in {"diagnostics"}:
            raise ValueError("device must be active for this operation")
        job = DeviceJob(
            organization_id=device.organization_id,
            device_id=device.id,
            job_type=job_type,
            payload=payload,
            requested_by=requested_by,
        )
        self.session.add(job)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=requested_by,
                action="device.job.queued",
                object_type="device_job",
                object_id=str(job.id),
                after_data={"job_type": job_type, "device_id": str(device.id)},
                context_data={"organization_id": str(device.organization_id)},
            )
        )
        return job


class DeviceJobProcessor:
    def __init__(
        self,
        session: Session,
        *,
        adapter_resolver: AdapterResolver,
        settings: Settings,
        archive_cipher: DeviceSecretCipher,
    ) -> None:
        self.session = session
        self.adapter_resolver = adapter_resolver
        self.settings = settings
        self.archive_cipher = archive_cipher
        self.platform = DevicePlatformService(session)

    def queued_jobs(self, *, limit: int = 25) -> tuple[DeviceJob, ...]:
        query = (
            select(DeviceJob)
            .where(DeviceJob.status == "queued")
            .order_by(DeviceJob.created_at, DeviceJob.id)
            .limit(limit)
        )
        if self.session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        return tuple(self.session.scalars(query).all())

    def run_once(self, *, limit: int = 25) -> tuple[DeviceJob, ...]:
        results: list[DeviceJob] = []
        for job in self.queued_jobs(limit=limit):
            self.process(job)
            results.append(job)
        return tuple(results)

    def process(self, job: DeviceJob) -> DeviceJob:
        if job.status != "queued":
            return job
        device = self.session.get(Device, job.device_id)
        job.status = "running"
        job.started_at = utc_now()
        self.session.flush()
        if not device or device.organization_id != job.organization_id:
            return self._fail(job, "device_not_found", "Registered device is unavailable.")
        try:
            adapter = self.adapter_resolver(device)
            with device_pull_lock(self.session, device.id) as locked:
                if not locked:
                    return self._fail(
                        job,
                        "device_locked",
                        "Another worker is already operating on this device.",
                    )
                result = self._execute(job, device, adapter)
            job.result = result
            job.status = "succeeded"
            job.error_code = None
            job.error_detail = None
            job.ended_at = utc_now()
            self.session.add(
                AuditEvent(
                    actor_user_id=job.requested_by,
                    action="device.job.succeeded",
                    object_type="device_job",
                    object_id=str(job.id),
                    after_data={"job_type": job.job_type, "result": result},
                    context_data={"organization_id": str(job.organization_id)},
                )
            )
        except Exception as exc:
            self._fail(
                job,
                type(exc).__name__[:100],
                "Device operation failed; see sanitized job status and worker logs.",
            )
        self.session.flush()
        return job

    def _fail(self, job: DeviceJob, code: str, detail: str) -> DeviceJob:
        job.status = "failed"
        job.error_code = code[:100]
        job.error_detail = detail[:1000]
        job.ended_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=job.requested_by,
                action="device.job.failed",
                object_type="device_job",
                object_id=str(job.id),
                after_data={"job_type": job.job_type, "error_code": job.error_code},
                context_data={"organization_id": str(job.organization_id)},
            )
        )
        return job

    def _execute(
        self,
        job: DeviceJob,
        device: Device,
        adapter: DeviceAdapter,
    ) -> dict:
        if job.job_type == "diagnostics":
            diagnostics = adapter.diagnostics()
            snapshot = DeviceDiagnosticSnapshot(
                organization_id=device.organization_id,
                device_id=device.id,
                reachable=diagnostics.reachable,
                firmware_version=diagnostics.firmware_version,
                device_time=diagnostics.device_time,
                message=diagnostics.message,
                diagnostic_data=dict(diagnostics.metadata),
                observed_at=diagnostics.observed_at,
            )
            self.session.add(snapshot)
            device.last_seen_at = diagnostics.observed_at if diagnostics.reachable else device.last_seen_at
            self.session.flush()
            return {
                "diagnostic_id": str(snapshot.id),
                "reachable": diagnostics.reachable,
                "firmware_version": diagnostics.firmware_version,
            }

        if job.job_type == "immediate_pull":
            pull = DevicePullCoordinator(
                self.session,
                max_attempts=self.settings.device_pull_max_attempts,
            ).pull_device(
                device=device,
                adapter=adapter,
                mode="immediate",
                requested_by=job.requested_by,
            )
            if pull.status != "succeeded":
                raise RuntimeError(pull.error_code or "device pull failed")
            return {
                "pull_session_id": str(pull.id),
                "ingested_count": pull.ingested_count,
                "duplicate_count": pull.duplicate_count,
            }

        if job.job_type == "historical_pull":
            start_at = _parse_datetime(job.payload.get("start_at"), "start_at")
            end_at = _parse_datetime(job.payload.get("end_at"), "end_at")
            if end_at < start_at:
                raise ValueError("historical pull end cannot be before start")
            if end_at - start_at > timedelta(days=366):
                raise ValueError("historical pull range cannot exceed 366 days")
            pull_method = getattr(adapter, "pull_punches")
            batch = pull_method(cursor=None, start_at=start_at, end_at=end_at)
            pull_session = DevicePullSession(
                organization_id=device.organization_id,
                device_id=device.id,
                requested_by=job.requested_by,
                mode="immediate",
                status="running",
                attempt_count=1,
            )
            self.session.add(pull_session)
            self.session.flush()
            inserted, duplicates = self.platform.ingest_punches(
                device=device,
                punches=batch.punches,
                pull_session=pull_session,
            )
            pull_session.ingested_count = inserted
            pull_session.duplicate_count = duplicates
            pull_session.cursor_after = batch.next_cursor
            pull_session.status = "succeeded"
            pull_session.ended_at = utc_now()
            device.last_seen_at = pull_session.ended_at
            return {
                "pull_session_id": str(pull_session.id),
                "historical": True,
                "ingested_count": inserted,
                "duplicate_count": duplicates,
            }

        if job.job_type == "sync_users":
            capabilities = adapter.capabilities()
            if not capabilities.list_users:
                raise ValueError("device adapter does not support user inventory")
            created, updated = self.platform.sync_device_users(
                device=device,
                users=adapter.list_users(),
            )
            return {"created": created, "updated": updated}

        if job.job_type == "push_user":
            capabilities = adapter.capabilities()
            push_user = getattr(adapter, "push_user", None)
            if not capabilities.push_users or push_user is None:
                raise ValueError("device adapter does not support user enrollment")
            external_user_id = str(job.payload.get("external_user_id") or "").strip()
            display_name = str(job.payload.get("display_name") or "").strip() or None
            if not external_user_id:
                raise ValueError("external_user_id is required")
            record = push_user(
                DeviceUserRecord(
                    external_user_id=external_user_id,
                    display_name=display_name,
                    privilege="user",
                ),
                overwrite=False,
            )
            self.platform.sync_device_users(device=device, users=(record,))
            return {"external_user_id": record.external_user_id}

        if job.job_type == "migrate_user":
            target_id = UUID(str(job.payload.get("target_device_id")))
            external_user_id = str(job.payload.get("external_user_id") or "").strip()
            target = self.session.get(Device, target_id)
            if not target or target.organization_id != device.organization_id:
                raise LookupError("target device not found")
            source_user = self.session.scalar(
                select(DeviceUser).where(
                    DeviceUser.device_id == device.id,
                    DeviceUser.external_user_id == external_user_id,
                )
            )
            if not source_user:
                raise LookupError("source device user not found")
            with device_pull_lock(self.session, target.id) as target_locked:
                if not target_locked:
                    raise RuntimeError("target device is busy")
                target_adapter = self.adapter_resolver(target)
                target_users = {
                    item.external_user_id: item for item in target_adapter.list_users()
                }
                if external_user_id in target_users:
                    raise ValueError(
                        "target device already contains this user; migration will not overwrite"
                    )
                push_user = getattr(target_adapter, "push_user", None)
                if push_user is None or not target_adapter.capabilities().push_users:
                    raise ValueError("target device does not support user enrollment")
                migrated = push_user(
                    DeviceUserRecord(
                        external_user_id=source_user.external_user_id,
                        display_name=source_user.display_name,
                        privilege=source_user.privilege,
                        active=source_user.active,
                    ),
                    overwrite=False,
                )
                self.platform.sync_device_users(device=target, users=(migrated,))
            return {
                "source_device_id": str(device.id),
                "target_device_id": str(target.id),
                "external_user_id": migrated.external_user_id,
            }

        if job.job_type == "archive_user":
            export_archive = getattr(adapter, "export_user_archive", None)
            if export_archive is None or not adapter.capabilities().biometric_templates:
                raise ValueError("device adapter does not support encrypted user archive export")
            external_user_id = str(job.payload.get("external_user_id") or "").strip()
            if not external_user_id:
                raise ValueError("external_user_id is required")
            raw = export_archive(external_user_id)
            digest = hashlib.sha256(raw).hexdigest()
            key_id, ciphertext = self.archive_cipher.encrypt(
                {"archive_base64": base64.b64encode(raw).decode()}
            )
            archive = DeviceIdentityArchive(
                organization_id=device.organization_id,
                device_id=device.id,
                external_user_id=external_user_id,
                key_id=key_id,
                ciphertext=ciphertext,
                content_sha256=digest,
                created_by=job.requested_by,
            )
            self.session.add(archive)
            self.session.flush()
            return {
                "archive_id": str(archive.id),
                "external_user_id": external_user_id,
                "content_sha256": digest,
            }

        if job.job_type == "restore_user":
            archive_id = UUID(str(job.payload.get("archive_id")))
            archive = self.session.get(DeviceIdentityArchive, archive_id)
            if not archive or archive.organization_id != device.organization_id:
                raise LookupError("device archive not found")
            import_archive = getattr(adapter, "import_user_archive", None)
            if import_archive is None or not adapter.capabilities().biometric_templates:
                raise ValueError("device adapter does not support encrypted archive restore")
            secret = self.archive_cipher.decrypt(
                key_id=archive.key_id,
                ciphertext=archive.ciphertext,
            )
            raw = base64.b64decode(secret["archive_base64"], validate=True)
            if hashlib.sha256(raw).hexdigest() != archive.content_sha256:
                raise ValueError("device archive integrity check failed")
            restored = import_archive(raw, overwrite=False)
            self.platform.sync_device_users(device=device, users=(restored,))
            return {
                "archive_id": str(archive.id),
                "external_user_id": restored.external_user_id,
            }

        raise ValueError("unsupported device job type")
