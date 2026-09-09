import argparse
import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device
from hajiriflow.db.models.device_baseline import DeviceRuntimeConfiguration
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.identity_lifecycle import DeviceIdentityLifecycleService
from hajiriflow.device_platform.operations import DeviceOperationService
from hajiriflow.device_platform.pull import DevicePullCoordinator
from hajiriflow.device_platform.runtime import (
    build_device_secret_cipher,
    resolve_registered_adapter,
)

LOGGER = logging.getLogger("hajiriflow.worker")
MAX_SCHEDULED_DEVICES_PER_CYCLE = 500


def utc_now() -> datetime:
    return datetime.now(UTC)


def _scheduled_devices(session) -> list[Device]:
    return list(
        session.scalars(
            select(Device)
            .where(Device.status == "active")
            .order_by(Device.id)
            .limit(MAX_SCHEDULED_DEVICES_PER_CYCLE)
        ).all()
    )


def _is_due(session, device: Device, now: datetime) -> bool:
    runtime = session.get(DeviceRuntimeConfiguration, device.id)
    last_success = runtime.last_successful_pull_at if runtime else None
    last_observed = last_success or device.last_seen_at
    if last_observed is None:
        return True
    if last_observed.tzinfo is None:
        last_observed = last_observed.replace(tzinfo=UTC)
    return last_observed <= now - timedelta(seconds=device.pull_interval_seconds)


def run_cycle() -> dict[str, int]:
    settings = get_settings()
    session = get_session_factory()()
    counters = {
        "queued_operations": 0,
        "identity_actions": 0,
        "scheduled_pulls": 0,
        "scheduled_failures": 0,
    }
    try:
        def resolver(device: Device):
            return resolve_registered_adapter(
                session=session,
                settings=settings,
                device=device,
            )

        operations = DeviceOperationService(
            session,
            max_attempts=settings.device_pull_max_attempts,
        )
        processed = operations.process_pending(adapter_resolver=resolver, limit=25)
        counters["queued_operations"] = len(processed)

        try:
            cipher = build_device_secret_cipher(settings)
        except ValueError:
            cipher = None
        identity_actions = DeviceIdentityLifecycleService(session).process_approved(
            adapter_resolver=resolver,
            cipher=cipher,
            limit=20,
        )
        counters["identity_actions"] = len(identity_actions)

        coordinator = DevicePullCoordinator(
            session,
            max_attempts=settings.device_pull_max_attempts,
        )
        now = utc_now()
        for device in _scheduled_devices(session):
            if not _is_due(session, device, now):
                continue
            adapter = resolver(device)
            if adapter is None:
                continue
            try:
                pull = coordinator.pull_device(
                    device=device,
                    adapter=adapter,
                    mode="scheduled",
                )
                counters["scheduled_pulls"] += 1
                if pull.status == "succeeded":
                    runtime = operations.runtime_configuration(
                        organization_id=device.organization_id,
                        device_id=device.id,
                    )
                    runtime.last_successful_pull_at = pull.ended_at
                elif pull.status == "failed":
                    counters["scheduled_failures"] += 1
            except Exception:
                counters["scheduled_failures"] += 1
                LOGGER.exception(
                    "scheduled device pull failed",
                    extra={"device_id": str(device.id)},
                )
        session.commit()
        return counters
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HajiriFlow device/background work.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one bounded worker cycle and exit.",
    )
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    while True:
        try:
            counters = run_cycle()
            LOGGER.info("worker cycle completed: %s", counters)
        except Exception as exc:
            LOGGER.error("worker cycle failed: %s", type(exc).__name__)
        if args.once:
            return 0
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
