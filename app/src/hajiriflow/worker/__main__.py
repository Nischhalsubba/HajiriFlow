import logging
import time

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.worker.scheduler import DevicePullScheduler


def resolve_adapter(_device: Device) -> DeviceAdapter | None:
    """Return an adapter only when concrete supported hardware is registered.

    The repository deliberately ships no vendor adapter. A deployment that supports
    actual hardware must replace/register this resolver with a reviewed adapter rather
    than guessing a device protocol from vendor/model strings.
    """

    return None


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("hajiriflow.worker")
    logger.info("HajiriFlow device scheduler started")

    while True:
        session = get_session_factory()()
        try:
            results = DevicePullScheduler(
                session,
                adapter_resolver=resolve_adapter,
                max_attempts=settings.device_pull_max_attempts,
                logger=logger,
            ).run_once()
            session.commit()
            if results:
                status_counts: dict[str, int] = {}
                for result in results:
                    status_counts[result.status] = status_counts.get(result.status, 0) + 1
                logger.info("Device scheduler cycle completed: statuses=%s", status_counts)
        except Exception as exc:
            session.rollback()
            logger.error(
                "Device scheduler cycle failed: error_type=%s",
                type(exc).__name__,
            )
        finally:
            session.close()

        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
