"""Alembic migration environment.

Loads our SQLAlchemy metadata and DB URL from app settings so that
``alembic upgrade head`` works without duplicating configuration.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import all models so they're registered on Base.metadata before autogenerate runs.
# Add new model modules here as they're created.
from app.models import (  # noqa: F401
    work_order,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the URL from alembic.ini with the one from settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def _include_object(object_, name, type_, reflected, compare_to):
    """Tell autogenerate to ignore tables Alembic doesn't own.

    Procrastinate manages its own schema via `procrastinate schema
    --apply`; if we don't filter them out, autogenerate sees them as
    "extra" tables in the DB and proposes dropping them on the next
    migration. Same will apply to any other tool that creates its own
    tables in our database in the future.
    """
    return not (type_ == "table" and name and name.startswith("procrastinate_"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
