"""Database session factories for sync and async usage."""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _transaction_pooler(url: str) -> str:
    """Route async query traffic through Supabase's transaction-mode pooler
    (:6543) instead of session mode (:5432).

    Session mode caps total clients at 15 — shared across both web machines,
    the worker, AND Procrastinate — which we saturate, causing intermittent
    `EMAXCONNSESSION` 500s. Transaction mode has a far higher client cap.
    Procrastinate stays on session mode (it needs a persistent LISTEN/NOTIFY
    connection, which transaction pooling can't provide). Only the Supabase
    pooler host is rewritten; local/direct URLs are untouched.
    """
    return url.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")


# Synchronous engine and session — used by Alembic and scripts
sync_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Async engine and session — used by FastAPI request handlers and workers.
# Runs through the transaction-mode pooler; asyncpg's prepared-statement
# cache is disabled because transaction pooling can't keep server-side
# prepared statements across pooled connections.
async_engine = create_async_engine(
    _transaction_pooler(settings.DATABASE_URL_ASYNC),
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    # statement_cache_size=0 disables asyncpg's prepared-statement cache;
    # prepared_statement_cache_size=0 disables SQLAlchemy's dialect-level
    # cache. BOTH are required — transaction pooling rotates the underlying
    # server connection, so a cached prepared statement may not exist on it.
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    echo=settings.DEBUG,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def get_db() -> Generator[Session]:
    """Yield a synchronous DB session (for scripts and Alembic)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    """Yield an async DB session (for FastAPI dependencies and async workers)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
