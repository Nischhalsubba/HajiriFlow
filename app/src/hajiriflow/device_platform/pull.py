import hashlib
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from hajiriflow.db.models.device import Device, DevicePullSession
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.service import DevicePlatformService


def utc_now() -> datetime:
    return datetime.now(UTC)


def _advisory_lock_key(device_id: UUID) -> int:
    raw = hashlib.sha256(device_id.bytes).digest()[:8]
    value = int.from_bytes(raw, byteorder="big", signed=False)
    return value - (1 << 64) if value >= (1 << 63) else value


@contextmanager
def device_pull_lock(session: Session, device_id: UUID):
    """Use a PostgreSQL advisory lock so only one worker pulls a device at a time."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        yield True
        return

    lock_key = _advisory_lock_key(device_id)
    acquired = bool(
        session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
    )
    try:
        yield acquired
    finally:
        if acquired:
            session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})


class DevicePullCoordinator:
    def __init__(self, session: Session, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.session = session
        self.max_attempts = max_attempts
        self.service = DevicePlatformService(session)

    def _latest_cursor(self, device_id: UUID) -> str | None:
        return self.session.scalar(
            select(DevicePullSession.cursor_after)
            .where(
                DevicePullSession.device_id == device_id,
                DevicePullSession.status == "succeeded",
            )
            .order_by(DevicePullSession.started_at.desc())
            .limit(1)
        )

    def pull_device(
        self,
        *,
        device: Device,
        adapter: DeviceAdapter,
        mode: str = "scheduled",
        requested_by: UUID | None = None,
    ) -> DevicePullSession:
        if device.status != "active":
            raise ValueError("disabled devices cannot be pulled")
        if adapter.adapter_key != device.adapter_key:
            raise ValueError("device adapter does not match the registered adapter key")
        if mode not in {"scheduled", "immediate"}:
            raise ValueError("unsupported pull mode")

        cursor = self._latest_cursor(device.id)
        pull_session = DevicePullSession(
            organization_id=device.organization_id,
            device_id=device.id,
            requested_by=requested_by,
            mode=mode,
            status="running",
            cursor_before=cursor,
            attempt_count=1,
        )
        self.session.add(pull_session)
        self.session.flush()

        with device_pull_lock(self.session, device.id) as acquired:
            if not acquired:
                pull_session.status = "skipped"
                pull_session.error_code = "device_locked"
                pull_session.error_detail = "Another worker is already pulling this device."
                pull_session.ended_at = utc_now()
                self.session.flush()
                return pull_session

            for attempt in range(1, self.max_attempts + 1):
                pull_session.attempt_count = attempt
                try:
                    batch = adapter.pull_punches(cursor=cursor)
                    inserted, duplicates = self.service.ingest_punches(
                        device=device,
                        punches=batch.punches,
                        pull_session=pull_session,
                    )
                    capabilities = adapter.capabilities()
                    if capabilities.list_users:
                        self.service.sync_device_users(
                            device=device,
                            users=adapter.list_users(),
                        )
                    pull_session.ingested_count += inserted
                    pull_session.duplicate_count += duplicates
                    pull_session.cursor_after = batch.next_cursor
                    pull_session.status = "succeeded"
                    pull_session.error_code = None
                    pull_session.error_detail = None
                    pull_session.ended_at = utc_now()
                    device.last_seen_at = pull_session.ended_at
                    self.session.flush()
                    return pull_session
                except Exception as exc:
                    if attempt < self.max_attempts:
                        continue
                    pull_session.status = "failed"
                    pull_session.error_code = type(exc).__name__[:100]
                    pull_session.error_detail = "Device pull failed after bounded retries."
                    pull_session.ended_at = utc_now()
                    self.session.flush()
                    return pull_session

        return pull_session

    def pull_many(
        self,
        jobs: Iterable[tuple[Device, DeviceAdapter]],
    ) -> tuple[DevicePullSession, ...]:
        """Pull every device independently so one failure never blocks another."""
        results: list[DevicePullSession] = []
        for device, adapter in jobs:
            try:
                result = self.pull_device(device=device, adapter=adapter)
            except Exception:
                result = DevicePullSession(
                    organization_id=device.organization_id,
                    device_id=device.id,
                    mode="scheduled",
                    status="failed",
                    attempt_count=1,
                    error_code="coordinator_error",
                    error_detail="Device pull could not be started.",
                    ended_at=utc_now(),
                )
                self.session.add(result)
                self.session.flush()
            results.append(result)
        return tuple(results)
