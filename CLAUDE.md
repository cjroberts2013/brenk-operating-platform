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
above, and the reference shell at `docs/design/dashboard-shell.tsx`.
Follow the build order in the Dashboard Plan section. The next concrete
task is **Supabase Auth login flow** — sign-in page, session handling,
sign-out, user's email in the top bar.

After that, the API client wrapper, then the Work Orders list as the
first real data page.

**Other backend cleanup deferred for now:**
- ~10 pre-existing ruff errors in `config.py`, `migrations/env.py`,
  and the autogenerated initial migration.
- Fly.io deployment exercise (configs already exist).
- `LICENSE` leftover merge-conflict markers in the working tree.
- Local `main` is several commits ahead of `origin/main` — push when
  you're ready (won't push without an explicit ask).

## Dashboard Plan (Phase 1 frontend)

Settled in two planning conversations (2026-05-16 and 2026-05-18). The
dashboard is a Next.js + React + Tailwind app under `frontend/`, backed
by our existing `/api/v1/work-orders/` API and authenticated via
Supabase Auth JWTs.

### Product framing

The dashboard's primary job is **keeping the pipeline moving** —
surfacing work orders that have stalled at any of the stages where
Brenk currently loses them. It is NOT just a viewer for SC data; it
tracks the full lifecycle from SC dispatch through Brenk's internal
workflow to invoice.

Daryl's current workflow (from his own description):
1. Email from SC requesting a WO — needs accept/decline (pink)
2. Daryl accepts in SC → dispatch confirmed (yellow). He always
   self-assigns within SC.
3. Daryl texts his Brenk sub-vendor — SC has no record of which
   sub-vendor is on the job. **This is where our tracking starts to
   matter.**
4. Vendor goes to site, ideally signs into CubeSmart's mobile app
   (GPS-tracked). Not all vendors comply.
5. Work completes → orange in SC (auto after 7 days or sooner if
   store closes manually)
6. Store confirms → green
7. Sue prints the green ones and puts them on a clipboard. Daryl
   reviews each, decides markup (min 65%, up to 200%) using his
   markup-board reference, then invoices in SC.

Top failure modes (where things get "lost"):
- Vendor assigned in our heads but never actually texted
- Vendor texted but didn't reply / no on-site confirmation
- Store auto-closes but Sue/Daryl misses the invoicing step
- Daryl pays a vendor on his phone and forgets to invoice

### Lifecycle stages

Daryl already lives in SC's color language — we adopt it verbatim and
layer Brenk-internal milestones on top.

| Stage | Color | Source of truth | Advanced by | Failure mode |
|---|---|---|---|---|
| Accept/Decline pending | Pink | SC | Daryl | Sits past deadline |
| Dispatch confirmed | Yellow | SC | Daryl | — |
| Sub-vendor assigned | Yellow + 👤 | **Brenk DB** | Daryl | Yellow forever |
| Vendor notified | Yellow + 💬 | **Brenk DB** | Daryl (texts) | Texted but silent |
| Vendor on-site | Yellow + 📍 | CubeSmart app (no signal to us) | Vendor | Vendor never signs in |
| Work complete | Orange | SC | Vendor / auto-7d | — |
| Closed by store | Green | SC | Store | Store forgets |
| Ready to invoice | Green + 💵 | **Brenk DB** | Sue | Sue's clipboard pile |
| Markup decided | Green + 💵✓ | **Brenk DB** | Daryl | Forgets to mark up |
| Invoiced | ✅ done | SC | Daryl | Vendor paid, never billed |

**The bold-italic stages are Brenk-internal and the biggest sources
of "lost" WOs today.** They don't exist in SC. They're our
differentiation.

### UI foundation

Tailwind UI "Dark sidebar with header" application shell. The raw
reference code lives at `docs/design/dashboard-shell.tsx`. Adapted
shell is `frontend/components/AppShell.tsx` (committed `c99495a`).

Other Tailwind UI components we'll reuse:
- Invoice detail layout (left content + right activity timeline) — for
  WO detail and the invoice queue detail
- Calendar component — for per-vendor calendar view
- Cashflow dashboard layout (top stat tiles + recent activity) — for
  the Dashboard page (stats become pipeline funnel counts)
- Application shell with header search — already in use

Charles has the React source for all of these via his Tailwind UI
subscription — request them as needed.

### Sidebar navigation

- Dashboard (pipeline funnel + stuck WOs)
- Work Orders (filterable/sortable table)
- Vendors (CRUD + workload view + calendar)
- Reports (placeholder until Phase 4 analytics)
- Settings (user + Daryl's markup-board reference)

### Pages, in build order

1. **Supabase Auth login flow.** Sign-in page, session handling,
   sign-out menu action, user's email in the top bar.
2. **API client wrapper.** Tiny typed fetch wrapper that attaches the
   Supabase JWT and redirects on 401.
3. **Work Orders list.** First real data page. Reads
   `/api/v1/work-orders/`. Columns: status badge, WO #, location,
   trade, vendor (with "Unassigned" highlighted), priority, NTE,
   scheduled, last updated, action menu. Filters: status, priority,
   vendor (incl. Unassigned), trade, free text. Default: open WOs
   only, sorted by stalest first.
4. **Work Order detail.** Two-column layout. Left: WO info + notes
   timeline (chronological feed). Right: **workflow checklist** with
   inline action buttons for each Brenk-internal stage (Assign vendor,
   Mark texted, Mark ready-to-invoice, etc.) + "Open in SC" deep
   links for stages SC owns.
5. **Backend: Vendors API.** New endpoints `GET/POST/PATCH/DELETE
   /api/v1/vendors`. Schema additions needed on the `vendors` table
   (see below).
6. **Vendors list + detail + add/edit.** Profile fields per the
   expanded model below. Vendor detail page shows their active WOs
   and a calendar of scheduled WOs.
7. **WO detail: vendor assignment wires up** to the real vendor pool.
8. **Dashboard.** Pipeline funnel (counts at each stage with avg
   age), "Stuck right now" panel, "Ready for action" panel. Replaces
   the placeholder home page.
9. **Invoice queue.** Tabbed list — "Ready to mark up" / "Marked up,
   ready to send" / "Sent" / "Paid". Invoice detail view matches the
   Tailwind UI invoice template (line items, totals, activity
   timeline). Markup helper surfaces Daryl's markup-board reference
   (captured once in Settings).

### Expanded Vendor model

Beyond what's in the current `vendors` table, we need:

| Field | Why |
|---|---|
| Contact preference | "SMS preferred", "Call first", "Email for big jobs" — drives notification UX |
| Payment terms | "Invoices weekly", "Hourly", "Flat per job", "Paid on completion" — affects invoicing flow |
| Mobile-app capable? | Yes/No — flags vendors who can't satisfy CubeSmart's GPS requirement |
| Markup notes | Free text — "premium work, run higher markup" |
| Communication notes | Free text — "Don't text after 6pm", "responds slowly" |
| Trade specializations | Multi-select from `trades` table |

Schema migration required. Goes with backend Vendors API work in
step 5 of the build order.

### Phase scope split

**Phase 1 (now):**
- Read from SC, write to Brenk-internal fields only
- All pipeline tracking (stage flags on WOs live in our DB)
- Vendor CRUD + workload + calendar
- Invoice queue replacing Sue's clipboard (markup decisions live in
  our DB; the actual invoice still gets entered in SC manually)

**Phase 1.5** (small follow-on, after SC write-API exploration):
- "Accept" / "Decline" buttons from our app write to SC
- Invoice line items push to SC
- Status change writes (limited — most stages SC computes itself)

**Phase 2:** Email integration — parse SC's emails, proactively
flag incoming requests before Daryl checks his inbox.

**Phase 3:** Vendor automation — Twilio for auto-texting, track
read/reply, reminder cadence.

**Phase 4:** AI assistance — compose vendor texts, flag at-risk WOs
proactively, suggest markup from past patterns.

### Open questions for the next session

- Does Charles have an existing vendor list to import, or start
  empty?
- How does Daryl want to express his markup-board rules? (Static
  reference card editable in Settings? Per-trade defaults? Per-vendor
  defaults? Just notes?)
- Color-coding pink/yellow/orange/green for SC stages — should we
  match SC's exact shades, or use cleaner Tailwind colors that map to
  the same conceptual stage?

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