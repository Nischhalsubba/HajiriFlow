import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.device import Device, DevicePullSession
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.pull import DevicePullCoordinator

AdapterResolver = Callable[[Device], DeviceAdapter | None]


def utc_now() -> datetime:
    return datetime.now(UTC)


class DevicePullScheduler:
    """Select due devices from the database and run bounded, isolated pulls."""

    def __init__(
        self,
        session: Session,
        *,
        adapter_resolver: AdapterResolver,
        max_attempts: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.adapter_resolver = adapter_resolver
        self.coordinator = DevicePullCoordinator(session, max_attempts=max_attempts)
        self.logger = logger or logging.getLogger("hajiriflow.worker.device-pulls")

    def due_devices(self, *, now: datetime | None = None) -> tuple[Device, ...]:
        observed_at = now or utc_now()
        devices = self.session.scalars(
            select(Device)
            .where(Device.status == "active")
            .order_by(Device.organization_id, Device.code)
        ).all()
        due: list[Device] = []
        for device in devices:
            last_attempt = self.session.scalar(
                select(DevicePullSession.started_at)
                .where(DevicePullSession.device_id == device.id)
                .order_by(DevicePullSession.started_at.desc())
                .limit(1)
            )
            if last_attempt is None:
                due.append(device)
                continue
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=UTC)
            next_attempt = last_attempt.astimezone(UTC) + timedelta(
                seconds=device.pull_interval_seconds
            )
            if next_attempt <= observed_at.astimezone(UTC):
                due.append(device)
        return tuple(due)

    def run_once(self, *, now: datetime | None = None) -> tuple[DevicePullSession, ...]:
        observed_at = now or utc_now()
        results: list[DevicePullSession] = []
        for device in self.due_devices(now=observed_at):
            try:
                adapter = self.adapter_resolver(device)
            except Exception as exc:
                adapter = None
                self.logger.error(
                    "Device adapter resolution failed: error_type=%s device_id=%s",
                    type(exc).__name__,
                    device.id,
                )
            if adapter is None:
                result = DevicePullSession(
                    organization_id=device.organization_id,
                    device_id=device.id,
                    mode="scheduled",
                    status="skipped",
                    attempt_count=1,
                    error_code="adapter_unavailable",
                    error_detail="No supported adapter is configured for this device.",
                    started_at=observed_at,
                    ended_at=observed_at,
                )
                self.session.add(result)
                self.session.flush()
                results.append(result)
                continue

            result = self.coordinator.pull_device(
                device=device,
                adapter=adapter,
                mode="scheduled",
            )
            results.append(result)
        return tuple(results)
