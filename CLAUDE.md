# CLAUDE.md

Context for Claude Code working on the Brenk Operating Platform.

## What This Project Is

A custom operations automation platform for **Brenk Facility Services, LLC**, a
family-owned general contracting business specializing in facility maintenance.
The platform integrates ServiceChannel (work order intake from clients),
QuickBooks (accounting), and the business's sub-vendor network into a single
AI-augmented dashboard.

The goal: reduce the daily admin burden currently sitting on the owner (Daryl
Brenk), making the business more efficient, more scalable, and ultimately more
sellable.

## Who's Working on This

- **Charles Roberts** — sole developer, family member, contracted at $50/hour
  during active development with bi-weekly invoices. Day job is iOS at Rocket;
  this is evening/weekend work.
- **Daryl Brenk** — owner of Brenk Facility Services, sole end user of the
  internal dashboard.

## Phase Sequencing

| Phase | Focus | Status |
|---|---|---|
| 1 | Foundation & ServiceChannel Integration | **In progress** |
| 2 | QuickBooks Integration & Invoice Automation | Not started |
| 3 | Vendor Communication Automation | Not started |
| 4 | Intelligence & Analytics | Not started |
| 5 | Public-Facing Business Website | Not started |

## Current State (Phase 1)

**Completed:**
- Project structure scaffolded (FastAPI + SQLAlchemy + Alembic + Procrastinate)
- ServiceChannel app registered in Sandbox2
- OAuth client built with token caching, refresh, retry, and rate-limit handling
- End-to-end auth verified via `scripts/test_sc_auth.py` — pulls live WOs successfully
- Database schema designed and committed as SQLAlchemy models
- Architecture and API docs in `docs/`
- Supabase project provisioned, `.env` configured with sync + async driver URLs
- Initial Alembic migration generated and applied — all 7 tables live in Supabase
- Work-order sync service implemented (`app/services/sync/`): transformers,
  upserter (with auto status-history), and orchestrator
- **SC client pagination** via `page`/`pageSize` with `iter_work_orders`
  async iterator and a 10K-record safety cap
- **Recurring schedule:** `scheduled_sync_work_orders` runs every 5 minutes
  via Procrastinate's `@periodic(cron=...)` decorator
- **REST API endpoints** for work orders: paginated list with filters,
  single-WO detail, and per-WO notes — all with eager-loaded
  Client/Location/Trade refs
- **Notes sync** with smart count-delta trigger (only fetches when SC
  reports more notes than we have stored); 2,930 notes successfully
  backfilled in sandbox
- **Supabase JWT auth** on all v1 endpoints via `HTTPBearer` security
  scheme — Swagger UI gets an "Authorize" button; `/health` remains open
- End-to-end verified: 327 work orders + 2,930 notes in Supabase,
  queryable via the authenticated API
- 34 tests passing (transformers, SC client, SC auth, API endpoints,
  JWT auth)

**Not yet done:**
- Next.js dashboard frontend (only remaining Phase 1 deliverable)
- Deployment to Fly.io / Vercel
- 10 pre-existing ruff errors in legacy files

## Tech Stack

- **Language:** Python 3.13
- **Backend:** FastAPI, Pydantic v2, structlog
- **Database:** Supabase (managed Postgres)
- **ORM:** SQLAlchemy 2.0 with Alembic migrations
- **Job queue:** Procrastinate (Postgres-backed, no Redis needed)
- **HTTP client:** httpx + tenacity for retries
- **Testing:** pytest + respx
- **Frontend (later):** Next.js + React + Tailwind on Vercel
- **Hosting:** Fly.io for backend + worker
- **AI (Phase 2+):** Anthropic Claude API

## Important Architectural Decisions

- **Postgres-as-queue (Procrastinate).** No Redis. Eliminates a managed service
  and gives transactional consistency between business data and job state.
- **`raw_data` JSONB on every SC-sourced table.** Preserves full upstream
  payloads for forward-compatibility and debugging.
- **Vendor model decoupled from ServiceChannel Providers.** Brenk tracks
  sub-vendors that aren't represented in SC.
- **All timestamps stored as UTC.** Local conversion at display time.
- **Status stored denormalized on `work_orders`.** No separate statuses table
  unless we need per-status metadata.
- **HTTPS to GitHub, not SSH.** SSH key setup deferred.

## ServiceChannel API — Known Quirks

Documented in `docs/architecture/servicechannel-api.md`. Highlights:

- OAuth password grant, tokens expire in 600 seconds, token endpoint is
  rate-limited to once per 5 seconds — caching is mandatory
- Sandbox2 contains real-shaped data including real entity names — treat with
  production-level confidentiality
- `Status.Primary` + `Status.Extended` together form the real status state
- Top-level `LocationId` is unreliable (often `0`) — use nested `Location.Id`
- Every timestamp comes in UTC + DTO pairs — store UTC
- **Attachments endpoint not yet found.** v1, v2, v3, and unversioned all
  return errors. Note attachments are reachable via the notes endpoint though.
- The `limit` param on `/v3/workorders` may not be honored as expected —
  observed returning 50 records when 5 were requested

## Volume Expectations

Brenk runs ~8 new WOs per day. The system is designed for this scale —
generous Supabase/Fly free tiers should cover years of operation. Don't
over-engineer for throughput.

## Repository Layout

```
brenk-operating-platform/
├── backend/                       # Python + FastAPI
│   ├── app/
│   │   ├── api/v1/endpoints/      # REST API routes
│   │   ├── core/                  # Config, logging, exceptions
│   │   ├── db/                    # Base, session, migrations
│   │   ├── models/                # SQLAlchemy ORM models
│   │   ├── schemas/               # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── servicechannel/    # SC API client + OAuth
│   │   │   └── sync/              # Sync orchestration
│   │   ├── workers/               # Procrastinate tasks
│   │   └── main.py                # FastAPI app
│   ├── scripts/                   # One-off utilities (test_sc_auth.py)
│   ├── tests/                     # pytest suite
│   └── pyproject.toml
├── frontend/                      # Next.js (to be scaffolded)
├── docs/
│   ├── architecture/              # Design docs
│   ├── api-samples/               # Real SC responses (gitignored if PII)
│   └── runbooks/                  # Setup and ops procedures
└── README.md
```

## Local Development

See `docs/runbooks/local-development.md` for the full setup. Quick reference:

```bash
cd backend
source .venv/bin/activate
# Run API:
uvicorn app.main:app --reload --port 8000
# Run worker:
procrastinate --app=app.workers.app worker
# Run tests:
pytest
# Verify SC auth:
python scripts/test_sc_auth.py
```

## Conventions

- **Format and lint:** `ruff check . && ruff format .`
- **Type hints:** required on all public functions; rely on Pydantic for
  validation at boundaries
- **Logging:** use `structlog`, never `print()`
- **Async:** all I/O is async; sync code allowed only in scripts and Alembic
- **Tests:** unit tests mock external calls with `respx`; integration tests
  may hit a local DB but never the real SC API

## What To Work On Next

Read `docs/architecture/overview.md` and the current week's section of the
Phase 1 plan (in the conversation history if available, or ask Charles).
The Phase 1 backend is functionally complete — only the dashboard and
operational concerns remain. The next concrete tasks are:

1. **Next.js dashboard scaffold.** Initialize the Next.js project under
   `frontend/`, set up Tailwind, render a "Hello world" page, wire up
   the Supabase JS client for auth (login flow). First commit goal:
   user can log in via Supabase, see their email, and see a placeholder
   work-orders page.
2. **First real dashboard page** — the work-orders list view consuming
   `GET /api/v1/work-orders/` with filtering and pagination. Status
   column should color-code (in-progress, completed, etc.). Click-through
   to a detail page.
3. **Push to GitHub.** Local `main` is ahead of `origin/main`; before
   Daryl sees anything we want the code backed up offsite.
4. **Cleanup pass.** ~10 pre-existing ruff errors in `config.py`,
   `migrations/env.py`, and the autogenerated initial migration. Small
   focused commit.
5. **Deployment prep.** Fly.io configs for the API and worker already
   exist (`fly.web.toml`, `fly.worker.toml`) but haven't been exercised
   end-to-end. Plan a deployment session before Daryl starts using the
   dashboard for real.

## Supabase Environment Strategy

Currently a **single Supabase project** is used for development. At end of
Phase 1, right before Daryl starts using the dashboard for real, spin up a
second free-tier Supabase project as production and keep the current one as
dev. Migrations should then be applied to both. (Supabase's built-in
branching feature requires the Pro plan, which we're not on.)

## Things To Avoid

- Don't commit `.env` or any file with real credentials
- Don't commit unscrubbed sandbox data to `docs/api-samples/` — it contains
  real client and location names
- Don't add Redis or RabbitMQ — Procrastinate replaces them
- Don't pin specific package versions in `pyproject.toml` unless we hit a real
  conflict — current pins are intentionally loose for resolver speed
- Don't introduce TypeScript code outside `frontend/`
- Don't change the Python target version away from 3.13 without coordinating

## Communication With Charles

Charles is the sole engineer and contact. He's working evenings and weekends
around a full-time iOS job and grad school. Sessions are intermittent. When
asking clarifying questions, prefer batched questions over single-question
back-and-forth. Charles tracks his hours for invoicing — when reaching natural
session boundaries, surface a brief summary of what was accomplished so it
can go into the bi-weekly invoice.