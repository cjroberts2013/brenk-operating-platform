"""Procrastinate application setup.

Procrastinate uses our Postgres database as the job queue backend, so no
separate Redis or RabbitMQ infrastructure is needed.

Run the worker:
    procrastinate --app=app.workers.app worker

Apply Procrastinate's own schema (one-time):
    procrastinate --app=app.workers.app schema --apply
"""

from procrastinate import PsycopgConnector
from procrastinate.app import App

from app.core.config import get_settings

settings = get_settings()

# Procrastinate needs a sync psycopg connection string (no driver suffix)
_db_url = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://").replace(
    "postgresql+asyncpg://", "postgresql://"
)

procrastinate_app = App(
    connector=PsycopgConnector(conninfo=_db_url),
    import_paths=["app.workers.tasks"],
)
