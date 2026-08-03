import os

os.environ.setdefault("HAJIRIFLOW_ENVIRONMENT", "test")
os.environ.setdefault("HAJIRIFLOW_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault(
    "HAJIRIFLOW_SESSION_SECRET",
    "test-secret-that-is-longer-than-thirty-two-characters",
)
os.environ.setdefault("HAJIRIFLOW_TIMEZONE", "Asia/Kathmandu")
