"""FastAPI application factory and entrypoint."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

import sentry_sdk
import structlog
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.v1 import api_router, public_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_async_db
from app.models.work_order import WorkOrder
from app.services.health import evaluate_sync_freshness

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

    @app.get("/health/sync-freshness", tags=["health"])
    async def sync_freshness(
        response: Response,
        db: Annotated[AsyncSession, Depends(get_async_db)],
    ) -> dict:
        """Dead-man's-switch for the worker's hourly WO sync.

        Returns 200 when the newest work_orders.last_synced_at is within
        SYNC_FRESHNESS_MAX_SECONDS, else 503. An external monitor (GitHub
        Actions cron) polls this and alerts if it goes 503 — so a silent
        worker stall surfaces in hours, not weeks. Public (no auth):
        exposes only a timestamp + boolean.
        """
        last = (await db.execute(select(func.max(WorkOrder.last_synced_at)))).scalar_one_or_none()
        result = evaluate_sync_freshness(
            last, datetime.now(UTC), settings.SYNC_FRESHNESS_MAX_SECONDS
        )
        if not result.fresh:
            response.status_code = 503
        return result.to_dict()

    return app


app = create_app()
