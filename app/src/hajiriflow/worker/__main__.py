import logging
import time

from hajiriflow.core.config import get_settings


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("hajiriflow.worker")
    logger.info("HajiriFlow worker started")

    # Deliberately idle until the database-backed job scheduler is implemented.
    # Device pulls must never read configuration from local JSON files.
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
