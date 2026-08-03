import os

import pytest

os.environ.setdefault("HAJIRIFLOW_ENVIRONMENT", "test")
os.environ.setdefault("HAJIRIFLOW_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault(
    "HAJIRIFLOW_SESSION_SECRET",
    "test-secret-that-is-longer-than-thirty-two-characters",
)
os.environ.setdefault("HAJIRIFLOW_TIMEZONE", "Asia/Kathmandu")
os.environ.setdefault("HAJIRIFLOW_LOGIN_MAX_ATTEMPTS", "3")
os.environ.setdefault("HAJIRIFLOW_LOGIN_WINDOW_SECONDS", "300")

from hajiriflow.core.config import get_settings  # noqa: E402
from hajiriflow.db import models  # noqa: E402, F401
from hajiriflow.db.base import Base  # noqa: E402
from hajiriflow.db.session import clear_database_caches, get_engine  # noqa: E402


@pytest.fixture
def database():
    get_settings.cache_clear()
    clear_database_caches()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    clear_database_caches()
    get_settings.cache_clear()
