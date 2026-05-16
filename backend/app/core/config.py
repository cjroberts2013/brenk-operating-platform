"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables via .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str
    DATABASE_URL_ASYNC: str

    # -------------------------------------------------------------------------
    # Supabase
    # -------------------------------------------------------------------------
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # -------------------------------------------------------------------------
    # ServiceChannel
    # -------------------------------------------------------------------------
    SC_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"
    SC_SANDBOX_LOGIN_URL: str = "https://sb2login.servicechannel.com"
    SC_SANDBOX_API_URL: str = "https://sb2api.servicechannel.com"
    SC_PRODUCTION_LOGIN_URL: str = "https://login.servicechannel.com"
    SC_PRODUCTION_API_URL: str = "https://api.servicechannel.com"
    SC_CLIENT_ID: str
    SC_CLIENT_SECRET: str
    SC_USERNAME: str
    SC_PASSWORD: str
    SC_SYNC_INTERVAL_SECONDS: int = 300
    SC_SYNC_LOOKBACK_HOURS: int = 24
    SC_REQUEST_TIMEOUT_SECONDS: int = 30
    SC_MAX_RETRIES: int = 3

    @computed_field
    @property
    def SC_LOGIN_URL(self) -> str:
        """Active login URL based on environment."""
        return (
            self.SC_PRODUCTION_LOGIN_URL
            if self.SC_ENVIRONMENT == "production"
            else self.SC_SANDBOX_LOGIN_URL
        )

    @computed_field
    @property
    def SC_API_URL(self) -> str:
        """Active API URL based on environment."""
        return (
            self.SC_PRODUCTION_API_URL
            if self.SC_ENVIRONMENT == "production"
            else self.SC_SANDBOX_API_URL
        )

    # -------------------------------------------------------------------------
    # Anthropic (Phase 2+)
    # -------------------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    SECRET_KEY: str = Field(default="", min_length=0)

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """ALLOWED_ORIGINS parsed as a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # type: ignore[call-arg]
