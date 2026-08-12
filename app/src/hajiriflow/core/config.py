from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    session_cookie_name: str = "hajiriflow_session"
    csrf_cookie_name: str = "hajiriflow_csrf"
    cookie_secure: bool = False
    cookie_same_site: Literal["lax", "strict", "none"] = "lax"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
    def validate_cookie_policy(self) -> "Settings":
        if self.cookie_same_site == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None requires secure cookies")
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("production requires secure cookies")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
