"""Procrastinate application setup.

Procrastinate uses our Postgres database as the job queue backend, so no
separate Redis or RabbitMQ infrastructure is needed.

Run the worker:
    procrastinate --app=app.workers.app.procrastinate_app worker

Apply Procrastinate's own schema (one-time):
    procrastinate --app=app.workers.app.procrastinate_app schema --apply

The `.procrastinate_app` suffix is required — procrastinate 3.x's
`--app` argument is a fully-dotted Python path including the
variable name. The gunicorn-style `module:variable` colon syntax
does NOT work here. So `app.workers.app.procrastinate_app` walks:
  1. Import `app.workers.app` module
  2. Get `procrastinate_app` attribute from it
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
