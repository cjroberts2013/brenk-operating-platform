# Local Development Setup

Step-by-step from a fresh clone to a running local environment.

## Prerequisites

- Python 3.13 (the target version — don't drift)
- Node 20 or later (for the frontend)
- A Supabase project with the database URL ready (use `Brenk Dev`)
- ServiceChannel sandbox credentials (client ID, secret, username, password)
- `flyctl` CLI installed (for production ops — see
  `docs/runbooks/production-deployment.md`)
- `vercel` CLI installed (for production frontend ops)
- `git` and a code editor

## 1. Clone and Open

```bash
cd "/Users/cjroberts/Documents/CharlesRobertsDesign/Brenk Operating Platform"
git remote add origin git@github.com:cjroberts2013/brenk-operating-platform.git
```

## 2. Set Up the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## 3. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

- `DATABASE_URL` and `DATABASE_URL_ASYNC` — from Supabase → Project Settings → Database
- `SC_CLIENT_ID` and `SC_CLIENT_SECRET` — from the ServiceChannel App Registration
- `SC_USERNAME` and `SC_PASSWORD` — Daryl's ServiceChannel sandbox credentials
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

Leave the rest at their defaults for now.

## 4. Verify ServiceChannel Auth

Before doing anything with the database, confirm the SC integration works:

```bash
python scripts/test_sc_auth.py
```

Expected output:
- Prints the configured environment (sandbox/production)
- Obtains an access token (shows the first 40 characters)
- Fetches 5 work orders and prints a summary of the first one
- Saves the response to `../docs/api-samples/workorder-list-sample.json`

If this fails, fix it before going further. Likely culprits:
- Wrong client ID/secret (check for trailing whitespace from copy-paste)
- Wrong username/password
- `SC_ENVIRONMENT` set to `production` when you have sandbox credentials

## 5. Apply Database Migrations

First, run Procrastinate's own schema setup (one time, creates the job queue tables):

```bash
procrastinate --app=app.workers.app.procrastinate_app schema --apply
```

> The `--app` flag needs the **full dotted path including the variable name**
> (`...procrastinate_app`), not just the module path. The Procrastinate CLI
> uses `App.from_path()` which expects the variable to be addressable.

Then apply our application migrations:

```bash
alembic upgrade head
```

If there are no migrations yet (early Phase 1), generate the initial one from the models:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## 6. Run the Backend

In one terminal:

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the auto-generated API docs.
Open `http://localhost:8000/health` to confirm the service is up.

## 7. Run the Worker

Open a second terminal:

```bash
source .venv/bin/activate
procrastinate --app=app.workers.app.procrastinate_app worker
```

The worker automatically picks up periodic tasks defined with
`@procrastinate_app.periodic(cron=...)`. As of this writing,
`scheduled_sync_work_orders` runs every 5 minutes — you should see
"scheduled sync tick" log lines as it fires.

To run a task ad-hoc (e.g., a backfill with a custom lookback):

```bash
procrastinate --app=app.workers.app.procrastinate_app defer \
  sync_work_orders --lookback-hours 720
```

## Running Tests

```bash
# All tests
pytest

# Just unit tests
pytest tests/unit

# With coverage
pytest -v --cov=app
```

## Linting and Formatting

```bash
ruff check .
ruff format .
mypy app
```

## Common Issues

**`ModuleNotFoundError: No module named 'app'`**
Make sure the virtualenv is activated and you installed with `pip install -e ".[dev]"`.

**Alembic can't find migrations**
Ensure you're running `alembic` from inside the `backend/` directory.

**SC auth returns 401**
Token endpoint is rate-limited to 1/5 seconds — if you're rapidly retrying, wait a moment. Also re-check that the Base64 encoding of `client_id:client_secret` has no trailing newline.

**Supabase connection times out**
Check that your Supabase project is in an active region and that the connection string uses the pooler endpoint (port 6543) for serverless-style usage, or direct (5432) for long-running connections like our worker.

## Useful Daily Commands

```bash
# Open an IPython shell with the app context loaded
ipython

# Generate a new migration after model changes
alembic revision --autogenerate -m "add foo column"

# Roll back the last migration
alembic downgrade -1

# Check current migration version
alembic current
```
