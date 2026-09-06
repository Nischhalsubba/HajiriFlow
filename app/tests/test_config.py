import pytest
from pydantic import ValidationError

from hajiriflow.core.config import Settings


VALID_SECRET = "a-valid-secret-that-is-longer-than-thirty-two-characters"


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
            cookie_secure=False,
            cors_origins="https://app.example.com",
        )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_protected_environments_reject_placeholder_session_secret(environment: str) -> None:
    with pytest.raises(ValidationError, match="non-placeholder session secret"):
        Settings(
            environment=environment,
            session_secret="replace-with-at-least-32-random-characters",
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
    ],
)
def test_production_rejects_insecure_or_loopback_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError, match="HTTPS, non-loopback CORS origins"):
        Settings(
            environment="production",
            session_secret=VALID_SECRET,
            cookie_secure=True,
            cors_origins=origin,
        )


def test_production_accepts_hardened_runtime_settings() -> None:
    settings = Settings(
        environment="production",
        session_secret=VALID_SECRET,
        cookie_secure=True,
        cors_origins="https://app.example.com,https://admin.example.com",
    )

    assert settings.allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
