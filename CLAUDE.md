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
| 5 | Public-Facing Business Website (CMS-driven) | Not started |

### Possible phase reorder (open decision, 2026-05-19)

Charles is considering promoting the storefront from Phase 5 to
**Phase 2**, ahead of QuickBooks integration. Rationale: storefront
is low complexity, ships quickly, gives Brenk an external face Daryl
can actually point clients at. Decide before starting Phase 2 work.

Tradeoff to weigh: QuickBooks/invoice automation is what directly
addresses Sue's clipboard + Daryl's markup-board burden, which is
the current operational pain point. Storefront is mostly marketing
value, less daily-grind relief. If Daryl needs the invoice workload
unloaded urgently, keep QuickBooks at Phase 2; if external presence
is the bigger near-term win, swap them.

### Phase 5 — Public-Facing Storefront (captured 2026-05-19)

The internal dashboard we're building lives at
`app.brenkfacilityservices.com` (or whatever domain Brenk eventually
uses), authenticated behind Supabase Auth. The base domain
(`brenkfacilityservices.com`) hosts a public marketing storefront —
contact info, services offered, project gallery, etc.

Key constraint: the storefront content must be editable from the
authenticated dashboard. Daryl (and Charles) update marketing copy
without touching code. Implementation will probably be:

- A new `storefront` table or set of tables in the Brenk DB (sections,
  blocks, images — whatever the content model needs)
- A "Storefront" tab in the dashboard sidebar for editing
- The public site fetches content from the same FastAPI backend (read-
  only, no auth required for the public endpoints) and renders it via
  Next.js static-site-generation or server-side rendering, rebuilt on
  content change

Open architectural decision (defer to Phase 5):
- Same Next.js project with hostname-based routing, OR two separate
  Next.js projects sharing the API. Probably the latter — cleaner
  deployment boundaries, simpler caching strategy for the public site.

Auth scoping works correctly out of the box: cookies set by
`app.<domain>` are not shared with the base domain, so the storefront
stays public and the dashboard stays locked.

## Current State (Phase 1)

**Completed (backend):**
- Project structure scaffolded (FastAPI + SQLAlchemy + Alembic + Procrastinate)
- ServiceChannel app registered in Sandbox2
- OAuth client built with token caching, refresh, retry, and rate-limit handling
- Database schema designed and committed as SQLAlchemy models
- Supabase project provisioned, `.env` configured with sync + async driver URLs
- Initial Alembic migration generated and applied — all 7 tables live in Supabase
- Work-order sync service: transformers, upserter (with auto status-history),
  orchestrator. SC client pagination + 10K-record safety cap.
- Recurring schedule: `scheduled_sync_work_orders` runs every 5 minutes via
  Procrastinate's `@periodic(cron=...)` (worker must be running)
- REST API endpoints: paginated list (sorted by `sc_work_order_id` desc) with
  filters, single-WO detail, and per-WO notes, all with eager-loaded refs
- Notes sync with smart count-delta trigger
- **Supabase JWT auth supports both HS256 (tests + legacy) and ES256/RS256
  via JWKS** — handles Supabase's modern asymmetric signing keys
- Manual sync triggers: `POST /api/v1/work-orders/sync` and
  `POST /api/v1/vendors/sync`, plus `GET /api/v1/work-orders/sync-status`
  for the dashboard's "Last synced …" line
- Scheduled WO sync runs **hourly** (was every 5 min — Brenk gets
  ~8 WOs/day, hourly is plenty and is much friendlier on network
  budgets)
- Free-text `?q=` search param on `/api/v1/work-orders/` and
  `/api/v1/vendors/` — case-insensitive substring match across the
  columns an operator would type
- 34 backend tests passing
- Live data: ~341 work orders, ~2,000 notes in Supabase

**Completed (frontend):**
- Next.js 16 + React 19 + Tailwind 4 + App Router scaffolded under `frontend/`
- Tailwind UI "Dark sidebar with header" shell adapted into
  `components/AppShell.tsx` with real nav and Next 16's `proxy.ts` for
  session-refresh + auth-redirect
- Supabase Auth sign-in / sign-out flow — server-side session handling
  via `@supabase/ssr` cookie helpers
- Typed API client (`lib/api/`) — auto-attaches the access token, surfaces
  typed `ApiError` on non-2xx
- Work Orders list page (`/work-orders`) — filterable, paginated, color-coded
- Work Order detail page (`/work-orders/[id]`) — two-column layout with
  Details + Notes timeline + Workflow checklist + SC deep-link, plus
  inline sub-vendor assignment
- Vendors backend: expanded model (contact prefs, payment terms,
  `service_area`, mobile-app capable, markup/comm notes, trade
  specializations, `sc_user_id`), CRUD + `POST /api/v1/vendors/sync`
- Vendor sync from SC: pulls `/v3/odata/users`, matches by
  `sc_user_id` then by email (case-insensitive). Email-fallback is
  load-bearing for the sandbox → production cutover.
- Vendors page: list with sync-from-SC + add/edit modal (pill-chip
  trade picker with search + create-trade-inline), per-vendor detail
  page with monthly calendar of scheduled WOs
- Daryl's 12 real sub-vendors' contact data + service areas + trade
  specializations seeded into dev via
  `backend/scripts/seed_daryl_vendor_contacts.py` (idempotent;
  authoritative record of how the data was applied)
- "Sync now" button + "Last synced X ago · auto-syncs every hour"
  status line in the `/work-orders` page header
- Contextual top-bar search: filters the current list page as you
  type (debounced URL `?q=` push, race-condition-safe). Active on
  `/work-orders` and `/vendors`, hidden on other paths.

**Not yet done:**
- Dashboard pipeline-funnel home page (currently placeholder)
- Invoice queue page (replaces Sue's clipboard)
- Markup helper / Settings page (Daryl's markup-board rules)
- Junction table for multi-vendor-per-WO (current model is single
  `assigned_vendor_id`; deferred until pipeline funnel surfaces the need)
- Production Supabase cutover (export script ready at
  `backend/scripts/export_vendors_for_cutover.py`)
- Deployment to Fly.io / Vercel
- 10 pre-existing ruff errors in legacy backend files

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

Vendors (backend + page + sync + assignment) is done. Daryl's real
contact data + service areas + trade vocabulary are now in dev. Next
chunk is the **Dashboard pipeline funnel** and the **Invoice queue** —
the two pages that directly attack Daryl's "WO got lost" failure modes.

1. **Dashboard pipeline funnel.** Replaces the placeholder home page.
   Tailwind UI cashflow-dashboard layout: stat tiles for each lifecycle
   stage (pink / yellow / yellow+👤 / yellow+💬 / orange / green /
   green+💵 / invoiced) with counts + average age, plus a "Stuck right
   now" panel listing WOs sitting too long in any stage.
2. **Invoice queue.** Tabbed list — "Ready to mark up" / "Marked up,
   ready to send" / "Sent" / "Paid". Invoice detail view matches
   Tailwind UI's invoice template (line items, totals, activity).
   This is Sue's-clipboard replacement and directly unloads the
   biggest current admin burden.
3. **Markup helper.** Settings page captures Daryl's markup-board
   reference (per-trade defaults? Per-vendor defaults? Just notes?
   Open question for Daryl). Surfaces inline on invoice-detail.
4. **Junction table for multi-vendor-per-WO.** Today's model is a
   single `assigned_vendor_id`. Daryl sometimes splits one WO across
   two trades (locksmith + electrical, say) — migrate to a
   `wo_vendor_assignments` join table when the funnel work surfaces
   the need.
5. **Production cutover.** Spin up the second free-tier Supabase
   project, `alembic upgrade head`, run the worker once to seed
   `trades` and `vendors` from prod SC, then
   `python scripts/export_vendors_for_cutover.py | psql "$PROD..."`
   and click "Sync from ServiceChannel". Targeting end of Phase 1.

**Open questions for the next session:**
- How does Daryl want to express his markup-board rules? Static
  reference card editable in Settings? Per-trade default %?
  Per-vendor default %? Just free-text notes he can refer to?
  Becomes blocking when we start the invoice queue.
- Should the trades picker visually group Brenk-custom vs SC-catalog
  trades, or sort alphabetically together? Worth a UX call after
  Daryl actually uses it.

**Other items still deferred:**
- ~10 pre-existing ruff errors in `config.py`, `migrations/env.py`,
  and the autogenerated initial migration.
- Fly.io / Vercel deployment exercise (configs already exist).
- Local `main` is many commits ahead of `origin/main` — push when
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
- Don't run uvicorn without `--reload` in dev. Without it, backend
  source edits silently do nothing until a manual restart and the
  failure mode is exotic — FastAPI matches against the stale routing
  table while the new source sits on disk. The runbook documents the
  correct invocation.
- Don't add a literal route below `/{param}` in a FastAPI router.
  Path-param routes match first by registration order, so a literal
  registered after `/{work_order_id}` would be swallowed.
- Don't construct Pydantic response models manually if you can avoid
  it. `Schema.model_validate(orm_obj)` with `from_attributes=True`
  auto-picks new fields when the schema gains them. Manual
  `Schema(field=…)` constructors silently 500 the next time the
  schema adds a required field unless every caller is updated in
  lock-step.

## Communication With Charles

Charles is the sole engineer and contact. He's working evenings and weekends
around a full-time iOS job and grad school. Sessions are intermittent. When
asking clarifying questions, prefer batched questions over single-question
back-and-forth. Charles tracks his hours for invoicing — when reaching natural
session boundaries, surface a brief summary of what was accomplished so it
can go into the bi-weekly invoice.