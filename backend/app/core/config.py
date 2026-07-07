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
    # Echo every SQL statement to stdout. Off by default — it's a heavy
    # firehose that noticeably slows local request handling. Decoupled from
    # DEBUG so dev can keep DEBUG on without the query spam. Set SQL_ECHO=true
    # only when actively debugging queries.
    SQL_ECHO: bool = False

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
    SC_REQUEST_TIMEOUT_SECONDS: int = 30
    SC_MAX_RETRIES: int = 3
    # Signing key from the SC Provider Automation WebHooks page (per env).
    # Used to verify inbound webhook HMAC signatures. Empty until set;
    # an empty key makes every signature fail closed (see sc_webhook.py).
    SC_WEBHOOK_SIGNING_KEY: str = ""
    # Human-facing SC web portal, for deep links in emails. Must match the
    # frontend's NEXT_PUBLIC_SC_WEB_URL per environment (the prod host is
    # www.servicechannel.com — sc.servicechannel.com is dead, see CLAUDE.md).
    SC_SANDBOX_WEB_URL: str = "https://sb2.servicechannel.com"
    SC_PRODUCTION_WEB_URL: str = "https://www.servicechannel.com"

    @computed_field
    @property
    def SC_LOGIN_URL(self) -> str:  # noqa: N802 - settings field naming, mirrors the SC_* env vars
        """Active login URL based on environment."""
        return (
            self.SC_PRODUCTION_LOGIN_URL
            if self.SC_ENVIRONMENT == "production"
            else self.SC_SANDBOX_LOGIN_URL
        )

    @computed_field
    @property
    def SC_API_URL(self) -> str:  # noqa: N802 - settings field naming, mirrors the SC_* env vars
        """Active API URL based on environment."""
        return (
            self.SC_PRODUCTION_API_URL
            if self.SC_ENVIRONMENT == "production"
            else self.SC_SANDBOX_API_URL
        )

    @computed_field
    @property
    def SC_WEB_URL(self) -> str:  # noqa: N802 - settings field naming, mirrors the SC_* env vars
        """Active human-facing SC portal URL based on environment."""
        return (
            self.SC_PRODUCTION_WEB_URL
            if self.SC_ENVIRONMENT == "production"
            else self.SC_SANDBOX_WEB_URL
        )

    # -------------------------------------------------------------------------
    # AI provider keys (Phase 2+). Server-side secrets — never exposed to the
    # frontend. Empty by default so the app boots without them.
    # -------------------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    # Gemini model used for WO categorization. Flash Lite is fast + cheap.
    # Override via env/secret to track the exact current model id (e.g.
    # "gemini-flash-lite-latest" / "gemini-3.1-flash-lite").
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

    # -------------------------------------------------------------------------
    # Email (Resend) — powers the storefront "Request a Quote" form.
    # When RESEND_API_KEY is empty the quote endpoint still accepts and
    # logs submissions (so leads aren't lost) but skips the actual send.
    # QUOTE_FROM_EMAIL must be on a Resend-verified domain in prod; the
    # default `onboarding@resend.dev` only delivers to the account owner
    # until brenkfacilityservices.com is verified.
    # -------------------------------------------------------------------------
    # SQLAlchemy async-engine pool sizing. Kept small on purpose: Supabase's
    # session-mode pooler caps total clients at 15, shared across both web
    # machines AND the worker. Defaults here (3 base + 2 overflow = 5 max per
    # process) leave headroom under that cap (2 web + worker ≈ 9 idle, 15 peak)
    # so a deploy's migration and connection spikes don't hit EMAXCONNSESSION.
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2

    RESEND_API_KEY: str = ""
    QUOTE_FROM_EMAIL: str = "Brenk Facility Services <quotes@brenkfacilityservices.com>"
    QUOTE_TO_EMAIL: str = "daryl@brenkfacilityservices.com"
    # Sender for vendor work-order notification emails. Same verified domain
    # as QUOTE_FROM_EMAIL (domain verification covers every address @ it, so
    # no extra Resend setup needed) but a dedicated mailbox so vendors see a
    # purpose-built "from".
    VENDOR_FROM_EMAIL: str = "Brenk Facility Services <workorder@brenkfacilityservices.com>"
    # Recipient for the daily turnaround-deadline digest. Empty means
    # "fall back to QUOTE_TO_EMAIL" at the call site.
    REMINDER_TO_EMAIL: str = ""

    # -------------------------------------------------------------------------
    # SMS (Twilio) — powers vendor work-order notification texts. When the
    # credentials are empty, `send_sms` logs a warning and returns False
    # (the endpoint surfaces a "not configured" error) — same graceful
    # degradation as Resend. TWILIO_FROM_NUMBER is the purchased Twilio
    # number in E.164 form (e.g. +15125551234).
    # -------------------------------------------------------------------------
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    # Where dispatch-receipt texts go (E.164). Every successful vendor
    # notification (email or text) sends a short SMS receipt here — WO #,
    # vendor, channel, and which signed-in operator sent it — so Daryl keeps
    # a text trail even when someone else runs the platform. Empty = off.
    DISPATCH_RECEIPT_TO_PHONE: str = ""

    # -------------------------------------------------------------------------
    # Dashboard — public base URL of the authenticated frontend, used to
    # build "open this WO" links in outbound emails.
    # -------------------------------------------------------------------------
    DASHBOARD_BASE_URL: str = "https://app.brenkfacilityservices.com"

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
