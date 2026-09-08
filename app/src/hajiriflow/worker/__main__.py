import logging
import time

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.jobs import DeviceJobProcessor
from hajiriflow.device_platform.runtime import (
    device_secret_cipher_from_environment,
    resolve_device_adapter,
)
from hajiriflow.worker.scheduler import DevicePullScheduler


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("hajiriflow.worker")
    logger.info("HajiriFlow device scheduler started")

    try:
        device_cipher = device_secret_cipher_from_environment()
    except ValueError as exc:
        logger.error("Device worker cannot start: %s", exc)
        raise SystemExit(2) from exc

    while True:
        session = get_session_factory()()
        try:
            def resolver(device: Device) -> DeviceAdapter:
                return resolve_device_adapter(
                    session,
                    device,
                    settings=settings,
                    cipher=device_cipher,
                )

            jobs = DeviceJobProcessor(
                session,
                adapter_resolver=resolver,
                settings=settings,
                archive_cipher=device_cipher,
            ).run_once()
            results = DevicePullScheduler(
                session,
                adapter_resolver=resolver,
                max_attempts=settings.device_pull_max_attempts,
                logger=logger,
            ).run_once()
            session.commit()
            if jobs:
                job_statuses: dict[str, int] = {}
                for job in jobs:
                    job_statuses[job.status] = job_statuses.get(job.status, 0) + 1
                logger.info("Device job cycle completed: statuses=%s", job_statuses)
            if results:
                status_counts: dict[str, int] = {}
                for result in results:
                    status_counts[result.status] = status_counts.get(result.status, 0) + 1
                logger.info("Device scheduler cycle completed: statuses=%s", status_counts)
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
