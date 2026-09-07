import pytest
from pydantic import ValidationError

from hajiriflow.core.config import Settings

VALID_SECRET = "a-valid-secret-that-is-longer-than-thirty-two-characters"
VALID_DATABASE_URL = "postgresql+psycopg://service:secret@db.example.com:5432/hajiriflow"


def test_rejects_short_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(session_secret="short")


def test_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(
            session_secret=VALID_SECRET,
            timezone="Mars/Olympus_Mons",
        )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_protected_environments_require_secure_cookies(environment: str) -> None:
    with pytest.raises(ValidationError, match="requires secure cookies"):
        Settings(
            environment=environment,
            session_secret=VALID_SECRET,
            database_url=VALID_DATABASE_URL,
            cookie_secure=False,
            cors_origins="https://app.example.com",
        )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_protected_environments_reject_placeholder_session_secret(environment: str) -> None:
    with pytest.raises(ValidationError, match="non-placeholder session secret"):
        Settings(
            environment=environment,
            session_secret="replace-with-at-least-32-random-characters",
            database_url=VALID_DATABASE_URL,
            cookie_secure=True,
            cors_origins="https://app.example.com",
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://hajiriflow:hajiriflow@localhost:5432/hajiriflow",
        "postgresql+psycopg://service:secret@127.0.0.1:5432/hajiriflow",
        "sqlite+pysqlite:///./hajiriflow.db",
    ],
)
def test_production_rejects_local_or_development_database(database_url: str) -> None:
    with pytest.raises(ValidationError, match="non-local, non-development database URL"):
        Settings(
            environment="production",
            session_secret=VALID_SECRET,
            database_url=database_url,
            cookie_secure=True,
            cors_origins="https://app.example.com",
        )


@pytest.mark.parametrize(
    "origin",
    [
        "http://app.example.com",
        "http://localhost:5173",
        "https://localhost:5173",
        "https://127.0.0.1:5173",
        "https://app.example.com/api",
        "https://user:pass@app.example.com",
        "https://app.example.com?tenant=demo",
    ],
)
def test_production_rejects_insecure_or_noncanonical_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError, match="HTTPS, non-loopback CORS origins"):
        Settings(
            environment="production",
            session_secret=VALID_SECRET,
            database_url=VALID_DATABASE_URL,
            cookie_secure=True,
            cors_origins=origin,
        )


def test_production_accepts_hardened_runtime_settings() -> None:
    settings = Settings(
        environment="production",
        session_secret=VALID_SECRET,
        database_url=VALID_DATABASE_URL,
        cookie_secure=True,
        cors_origins="https://app.example.com/,https://admin.example.com",
    )

    assert settings.allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
