"""FastAPI application factory and entrypoint."""

from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app import __version__
from app.api.v1 import api_router, public_router
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    configure_logging()
    settings = get_settings()

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[FastApiIntegration()],
        )

    logger.info(
        "Application starting",
        version=__version__,
        env=settings.APP_ENV,
        sc_env=settings.SC_ENVIRONMENT,
    )

    yield

    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Brenk Operating Platform",
        description="Backend API for Brenk Facility Services operations automation.",
        version=__version__,
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    # Public router mounted at the same /api/v1 prefix but without
    # the JWT-auth dependency chain. Keep this list narrow — most
    # endpoints should require auth.
    app.include_router(public_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Basic health check — used by Fly.io and monitoring."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
