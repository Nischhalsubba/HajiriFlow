import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings, get_settings
from hajiriflow.db.models.device import Device
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.operations import DeviceOperationService
from hajiriflow.device_platform.runtime import resolve_registered_adapter
from hajiriflow.worker.scheduler import DevicePullScheduler


def adapter_resolver(
    session: Session,
    settings: Settings,
) -> Callable[[Device], DeviceAdapter | None]:
    def resolve(device: Device) -> DeviceAdapter | None:
        return resolve_registered_adapter(
            session=session,
            settings=settings,
            device=device,
        )

    return resolve


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("hajiriflow.worker")
    logger.info("HajiriFlow device scheduler started")

    while True:
        session = get_session_factory()()
        try:
            resolve = adapter_resolver(session, settings)
            operation_results = DeviceOperationService(
                session,
                max_attempts=settings.device_pull_max_attempts,
            ).process_pending(adapter_resolver=resolve)
            scheduled_results = DevicePullScheduler(
                session,
                adapter_resolver=resolve,
                max_attempts=settings.device_pull_max_attempts,
                logger=logger,
            ).run_once()
            session.commit()
            if operation_results or scheduled_results:
                status_counts: dict[str, int] = {}
                for result in (*operation_results, *scheduled_results):
                    status_counts[result.status] = status_counts.get(result.status, 0) + 1
                logger.info("Device worker cycle completed: statuses=%s", status_counts)
        except Exception as exc:
            session.rollback()
            logger.error(
                "Device worker cycle failed: error_type=%s",
                type(exc).__name__,
            )
        finally:
            session.close()

        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
