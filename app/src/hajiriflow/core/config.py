import json
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_UNSAFE_SESSION_SECRETS = {
    "replace-with-at-least-32-random-characters",
    "change-me-change-me-change-me-change-me",
}
KNOWN_UNSAFE_DATABASE_URLS = {
    "postgresql://hajiriflow:hajiriflow@localhost:5432/hajiriflow",
    "postgresql+psycopg://hajiriflow:hajiriflow@localhost:5432/hajiriflow",
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    """Runtime configuration loaded from HAJIRIFLOW_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="HAJIRIFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql://hajiriflow:hajiriflow@localhost:5432/hajiriflow"
    session_secret: str = Field(min_length=32)
    timezone: str = "Asia/Kathmandu"
    log_level: str = "INFO"
    session_ttl_minutes: int = Field(default=480, ge=15, le=43200)
    login_window_seconds: int = Field(default=900, ge=60, le=86400)
    login_max_attempts: int = Field(default=5, ge=2, le=50)
    worker_poll_seconds: int = Field(default=30, ge=5, le=3600)
    device_pull_max_attempts: int = Field(default=3, ge=1, le=10)
    device_secret_active_key_id: str = ""
    device_secret_keys_json: SecretStr = SecretStr("")
    session_cookie_name: str = "hajiriflow_session"
    csrf_cookie_name: str = "hajiriflow_csrf"
    cookie_secure: bool = False
    cookie_same_site: Literal["lax", "strict", "none"] = "lax"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        # Browsers serialize an Origin without a trailing slash. Canonicalizing
        # root origins here prevents a harmless configuration typo from causing
        # CORS mismatches while still rejecting origins that contain a path.
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def device_secret_keys(self) -> dict[str, str]:
        raw = self.device_secret_keys_json.get_secret_value().strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("device-secret keyring must be valid JSON") from exc
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) and key and value
            for key, value in payload.items()
        ):
            raise ValueError("device-secret keyring must map non-empty key IDs to keys")
        return payload

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Use the installed psycopg 3 driver for standard managed-Postgres URLs."""

        normalized = value.strip()
        if normalized.startswith("postgresql://"):
            return "postgresql+psycopg://" + normalized.removeprefix("postgresql://")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {value}") from exc
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return value

    @model_validator(mode="after")
    def validate_security_policy(self) -> "Settings":
        if self.cookie_same_site == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None requires secure cookies")

        protected_environment = self.environment in {"staging", "production"}
        if not protected_environment:
            return self

        if not self.cookie_secure:
            raise ValueError(f"{self.environment} requires secure cookies")

        if self.session_secret.strip().lower() in KNOWN_UNSAFE_SESSION_SECRETS:
            raise ValueError(f"{self.environment} requires a non-placeholder session secret")

        database_url = self.database_url.strip()
        parsed_database = urlparse(database_url)
        database_scheme = parsed_database.scheme.lower().split("+", 1)[0]
        database_host = (parsed_database.hostname or "").lower()
        if (
            database_url.lower() in KNOWN_UNSAFE_DATABASE_URLS
            or database_scheme == "sqlite"
            or database_host in LOOPBACK_HOSTS
        ):
            raise ValueError(
                f"{self.environment} requires a non-local, non-development database URL"
            )

        unsafe_origins: list[str] = []
        for origin in [item.strip() for item in self.cors_origins.split(",") if item.strip()]:
            parsed = urlparse(origin)
            hostname = (parsed.hostname or "").lower()
            has_non_origin_parts = bool(
                parsed.username
                or parsed.password
                or parsed.params
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            )
            if (
                parsed.scheme.lower() != "https"
                or hostname in LOOPBACK_HOSTS
                or not hostname
                or has_non_origin_parts
            ):
                unsafe_origins.append(origin)

        if unsafe_origins:
            joined = ", ".join(unsafe_origins)
            message = (
                f"{self.environment} requires canonical HTTPS, non-loopback CORS origins; "
                f"unsafe: {joined}"
            )
            raise ValueError(message)

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
