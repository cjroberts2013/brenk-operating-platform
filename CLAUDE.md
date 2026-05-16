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

Read `docs/architecture/overview.md`, the **Dashboard Plan** section
above, and the reference shell at `docs/design/dashboard-shell.tsx`. The
Phase 1 backend is functionally complete — only the dashboard and
operational concerns remain. The next concrete tasks are:

1. **Push to GitHub.** Local `main` is ahead of `origin/main`; before
   Daryl sees anything we want the code backed up offsite. Tiny warm-up.
2. **Next.js project scaffold.** Initialize under `frontend/`, install
   deps (next, react, @headlessui/react, @heroicons/react, tailwindcss,
   @supabase/supabase-js), set up Tailwind dark mode, hook up the
   reference shell as the app's layout component with our nav items
   (Dashboard / Work Orders / Vendors / Reports / Settings).
3. **Supabase Auth login flow.** Sign-in page → Supabase Auth → store
   session → redirect to dashboard. User's email shown in the top bar.
   Sign-out menu action.
4. **API client.** A tiny typed wrapper around fetch that attaches the
   Supabase JWT to every request and surfaces 401s as a re-login redirect.
5. **Work Orders list page.** First real data page; consumes
   `GET /api/v1/work-orders/`. Color-coded status. Pagination.
6. From here, follow the page build order in the **Dashboard Plan**
   section above.

**Other backend cleanup deferred for now:**
- ~10 pre-existing ruff errors in `config.py`, `migrations/env.py`,
  and the autogenerated initial migration. Small focused commit.
- Fly.io deployment exercise (configs already exist).
- `LICENSE` leftover merge-conflict markers in the working tree.

## Dashboard Plan (Phase 1 frontend)

Settled in a planning conversation on 2026-05-16. The dashboard is a
Next.js + React + Tailwind app under `frontend/`, backed by our existing
`/api/v1/work-orders/` API and authenticated via Supabase Auth JWTs.

**UI foundation:** Tailwind UI "Dark sidebar with header" application
shell. The raw reference code lives at
`docs/design/dashboard-shell.tsx` — adapt, don't copy verbatim.

**Sidebar navigation:**
- Dashboard (home — "needs attention" + today's schedule)
- Work Orders (filterable/sortable table)
- Vendors (CRUD on Brenk sub-vendors + per-vendor workload view)
- Reports (placeholder until Phase 4 analytics)
- Settings

The "Your teams" subsection in the reference shell becomes a recently-
viewed-vendors quick-jump list.

**Pages, in build order:**
1. **App shell + Supabase login flow.** User signs in via Supabase Auth,
   sees their email in the top bar, lands on a placeholder dashboard.
2. **Work Orders list.** Reads `/api/v1/work-orders/` with the existing
   filters (status, client, trade). Status column is color-coded.
   Sortable, paginated. Click → detail page.
3. **Work Order detail.** Reads `/api/v1/work-orders/{id}` and `/notes`.
   Renders the full notes thread inline.
4. **Vendors page.** CRUD on the Brenk `vendors` table. New API
   endpoints needed: `GET/POST/PATCH/DELETE /api/v1/vendors`. Per-vendor
   detail page shows the WOs currently assigned to that vendor.
5. **Vendor assignment on WO detail.** Brenk-internal only — picks from
   the Brenk vendor pool, writes to our DB, does NOT propagate to SC.
6. **Kanban / status board.** Cards grouped by primary status, reuses
   the list API.
7. **"Needs attention" home dashboard.** Stale WOs (scheduled date
   passed + still open; no update in N days for in-progress; approaching
   expiration). Color-coded urgency.
8. **Per-vendor calendar view.** Tailwind UI calendar component, shows
   each vendor's assigned WOs by date.

**Phase 1 scope:** read from SC, write only to Brenk-internal fields
(sub-vendor assignment, internal notes, internal flags). NO writes flow
back to SC in Phase 1.

**Phase 1.5 / early Phase 3:** add SC write-through for status changes
and client-visible notes. Requires an SC write-API exploration session
first — we have NOT mapped SC's `POST`/`PATCH` endpoints yet.

**Color-code statuses everywhere:** consistent palette across the WO
list, kanban, calendar, and detail page. Likely: IN PROGRESS = blue,
COMPLETED = green, OPEN = gray, EXPIRED/STALE = red/amber.

**Open question carried into the next session:**
- Does Charles have an existing vendor list (spreadsheet, contacts)
  to import, or do we start with an empty Vendors table and add as we
  go?

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