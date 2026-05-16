# Backend

FastAPI service for the Brenk Operating Platform.

## Structure

```
backend/
├── app/
│   ├── api/                 # FastAPI routers
│   │   └── v1/              # Versioned API endpoints
│   ├── core/                # Config, logging, security, exceptions
│   ├── db/                  # Database session, base, migrations
│   │   └── migrations/      # Alembic migration scripts
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic
│   │   ├── servicechannel/  # ServiceChannel API client
│   │   └── sync/            # Sync orchestration
│   ├── workers/             # Procrastinate background tasks
│   └── main.py              # FastAPI app entrypoint
├── scripts/                 # One-off utilities
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/            # Test data (real SC responses, scrubbed)
├── pyproject.toml
└── .env.example
```

## Local Setup

### Prerequisites

- Python 3.12+
- A Supabase project (database URL ready)
- ServiceChannel sandbox credentials

### Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Fill in values in .env
```

### Run database migrations

```bash
alembic upgrade head
```

### Run the API server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`.

### Run the worker

```bash
procrastinate --app=app.workers.app worker
```

### Run the scheduler

```bash
procrastinate --app=app.workers.app schedule
```

## Testing

```bash
pytest                          # all tests
pytest tests/unit               # unit tests only
pytest -v --cov=app             # with coverage
```

## Linting and Type Checking

```bash
ruff check .
ruff format .
mypy app
```

## Useful Scripts

```bash
# Test ServiceChannel authentication end-to-end
python scripts/test_sc_auth.py

# Pull a sample work order and save to docs/api-samples/
python scripts/fetch_sample.py --type=workorder --id=350200688
```
