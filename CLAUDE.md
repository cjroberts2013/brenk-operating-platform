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
- Dashboard pipeline funnel home page: five tiles (pending /
  dispatched / work complete / ready to invoice / invoiced) +
  "Stuck right now" panel. Tiles link into the WO list via a
  single `?stage=…` param that runs the exact same composite
  filter the dashboard uses for counting — guaranteed to match.
- Invoice queue at `/invoices` with four tabs (Ready to mark up /
  Marked up / Sent / Paid). Markup helper card on each WO detail
  page captures labor + material cost separately, applies a markup
  %, warns if total bill > NTE. Brenk-confidential fields never
  pushed to SC.
- Public marketing storefront at the bare domain
  (`brenkfacilityservices.com` once deployed) sourced from the
  same Next.js project via hostname-based rewrite in `proxy.ts`.
  Dashboard editor at `/storefront` lets Daryl edit hero, about,
  services, service area, contact, and footer. Singleton content
  row + ordered services list in the backend.

**Not yet done:**
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
   biggest current admin burden. Markup helper (below) surfaces
   inline here.
3. **Markup helper.** Per-trade default markup % captured in
   Settings, suggested (never auto-applied) on the invoice detail
   for the WO's trade. Full design captured in the "Markup Helper
   Design" section below — Daryl does the math in his head today
   so we'll need to iterate; this v1 is just a starting shape.
4. **SC employee → WO assignment mapping (research + spike).**
   In the SC web UI, Daryl can see which work orders are assigned
   to each employee. Our v3 API probe (May 19 session) found the
   per-WO `Assignee` field empty across all 341 sandbox WOs, so we
   concluded it wasn't reachable — but that conclusion may have
   been sandbox-specific. We need to:
     - Try `/v3/odata/users/{id}/...` and `/v3/odata/employees/{id}/...`
       variations to see if a per-employee WO list endpoint exists.
     - Check whether production SC has the Assignee field populated
       (it almost certainly does, since the web UI reads it).
     - If we can pull it, surface it on the vendor detail page as
       a "Tech-assigned in SC" panel next to our Brenk-native
       assignment. Two sources of truth that we can cross-reference
       when Daryl asks "did I tell the vendor about this one yet?"
   This is research, not implementation — capture findings in
   `docs/architecture/servicechannel-api.md` once we know more.
5. **Junction table for multi-vendor-per-WO.** Today's model is a
   single `assigned_vendor_id`. Daryl sometimes splits one WO across
   two trades (locksmith + electrical, say) — migrate to a
   `wo_vendor_assignments` join table when the funnel work surfaces
   the need.
6. **Production cutover.** Spin up the second free-tier Supabase
   project, `alembic upgrade head`, run the worker once to seed
   `trades` and `vendors` from prod SC, then
   `python scripts/export_vendors_for_cutover.py | psql "$PROD..."`
   and click "Sync from ServiceChannel". Targeting end of Phase 1.
   The SC employee→WO research above is a natural pairing for this
   step, since the sandbox data is unreliable.

**Open questions for the next session:** none currently blocking.

**Resolved (2026-05-21):**
- *Markup-board rule shape* — per-trade default markup % stored on
  the Trade model, surfaced as a suggestion on invoice detail with
  a manual override. Daryl edits the defaults table from Settings.
  See "Markup Helper Design" below. **This is v1. Daryl currently
  does the math in his head — expect to iterate as he uses it.**
- *Trades-picker grouping* — mix Brenk-custom and SC-catalog trades
  together alphabetically (no visual grouping). Their purpose in
  the modal is just to help Daryl identify the right vendor; the
  origin of the label doesn't matter to him operationally. **Already
  this way in the form modal — no work needed.**

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
- **Invoice line items push to SC** — `POST /invoices`. Endpoint
  confirmed to exist; spike plan + adjacent read endpoints (for
  validation upfront + auto-derive Sent/Approved/Paid state) live
  in `docs/architecture/servicechannel-api.md` → "Invoice endpoints
  — Phase 1.5 anchor". Once shipped, replaces the manual "Daryl
  types the total into SC's invoice form" step.
- Status change writes (limited — most stages SC computes itself)

**Phase 2:** Email integration — parse SC's emails, proactively
flag incoming requests before Daryl checks his inbox.

**Phase 3:** Vendor automation — Twilio for auto-texting, track
read/reply, reminder cadence.

**Phase 4:** AI assistance — compose vendor texts, flag at-risk WOs
proactively, suggest markup from past patterns.

### Markup Helper Design (v1)

Daryl currently does the markup calculation in his head. He has a
loose mental model (doors get more, plumbing gets less, etc.) and
his rule-of-thumb range is **65% minimum, 200% maximum**, with most
jobs landing somewhere in between. The goal of the markup helper is
NOT to automate the decision — it's to give Daryl a quick
"reasonable starting point" he can lean on instead of recomputing
from scratch every time, while keeping him fully in control.

**Decided 2026-05-21. Subject to iteration once Daryl uses it.**

#### Three different money numbers — keep them straight

This caused a real bug. Spelling it out:

| Field                              | Where it comes from | Visible to client? | Role |
|------------------------------------|---------------------|---------------------|------|
| `work_orders.nte`                  | SC (client sets it) | Yes (client owns it) | **Ceiling.** Brenk can't bill the client more than this. |
| `work_orders.brenk_labor_cost`     | Brenk operator enters after the sub-vendor bills Brenk | **No — Brenk-confidential.** Never pushed to SC. | Vendor's labor charge. |
| `work_orders.brenk_material_cost`  | Brenk operator enters after the sub-vendor bills Brenk | **No — Brenk-confidential.** Never pushed to SC. | Vendor's materials/parts charge. |
| `work_orders.brenk_markup_percent` | Brenk operator decides per job | **No — Brenk-confidential.** Never pushed to SC. | % on top of vendor subtotal. Brenk's margin. |

**Vendor subtotal** = labor + material. Stored separately so Phase 4
analytics can ask "where's the money going?" across trades and
vendors. Combined arithmetically when needed (the helper card
shows the subtotal as a derived line, and the invoice-queue table
shows it under "Vendor cost").

**Total bill** Brenk invoices the client =
`(brenk_labor_cost + brenk_material_cost) * (1 + brenk_markup_percent / 100)`,
and this must be `<=` NTE. The markup helper UI surfaces a red
warning when this constraint is violated; the backend lets you save
it anyway (Daryl might be entering values mid-edit) but operationally
it means the markup or one of the vendor costs needs to come down
before invoicing.

**Vendor costs are NOT auto-derived from NTE.** Different numbers,
different sources. The first cut of the markup helper auto-pulled
NTE as the cost basis — that was wrong. Labor + material are always
operator-entered from the vendor's actual bill.

#### Data model

Columns added 2026-05-21:

| Column                             | Type        | Notes                                |
|------------------------------------|-------------|--------------------------------------|
| `trades.default_markup_percent`    | NUMERIC     | e.g. 75.00 for 75%. NULL = no default. |
| `work_orders.brenk_labor_cost`     | NUMERIC     | Vendor's labor charge. **Brenk-confidential.** |
| `work_orders.brenk_material_cost`  | NUMERIC     | Vendor's materials charge. **Brenk-confidential.** |
| `work_orders.brenk_markup_percent` | NUMERIC     | Chosen markup %. **Brenk-confidential.** |
| `work_orders.brenk_marked_up_at`   | TIMESTAMPTZ | Auto-stamped on first markup set. |
| `work_orders.brenk_paid_at`        | TIMESTAMPTZ | Manual: "client paid Brenk." |

Why per-trade defaults on `trades`, not a separate `markup_rules` table:
- Daryl's mental model already keys off trade ("doors get more").
- One row per trade keeps the editing surface small (he just
  pulls up Settings and edits a table).
- If we ever need conditional rules ("per trade per client", "per
  vendor"), we can refactor later without losing the v1 data —
  the column just becomes the fallback.

The actual markup % Daryl chose on each WO is stored on the WO
itself, not the trade default — Phase 4 AI learns from real
choices, not from defaults that may never have matched reality.

#### Settings page

A "Markups" panel on Settings shows a table:

```
Trade                                Default %    Notes
-----------------------------------------------------------------
Backflow Inspections                       75    
Commercial Door Repair                     85    Higher — specialty
DOORS (SC catalog)                         85    
Electrical                                 70    
Flooring                                   75    
…
```

Sorted alphabetically (matching the trades picker). All trades
appear, both Brenk-custom and SC-catalog — they're functionally
equivalent for this purpose. Inline-editable; a save action per
row, no global "save all" so partial edits are safe. Empty
percentage = NULL = no suggestion offered (the invoice helper
falls through to "enter manually").

A small `notes` text field per row gives Daryl somewhere to jot
"premium work, +10%" or "this trade is always a flat fee, %
doesn't make sense" without inventing extra columns.

#### Invoice detail surface

On the invoice-detail view for a WO, render a "Markup helper" card
on the right rail (same column as the WO detail page's workflow
checklist):

```
┌─ Markup helper ──────────────────────────────┐
│  Suggested 85% (Commercial Door Repair)      │
│  🔒 Costs + markup stay private to Brenk;    │
│     never sent to ServiceChannel.            │
│                                              │
│  NTE (max billable to client)      $ 250.00  │
│  Labor cost   (vendor's labor)   $ [120.00]  │
│  Material cost (parts/materials) $ [ 60.00]  │
│  ─────────────────────────────────────────   │
│  Vendor cost (subtotal)            $ 180.00  │
│  Markup                          [ 38 ] %    │
│  ─────────────────────────────────────────   │
│  Total bill                        $ 248.40  │
│                                              │
│  [   Save   ]   [Clear markup]               │
└──────────────────────────────────────────────┘
```
Labor + material are tracked separately so Phase 4 analytics can
slice spend by category. The subtotal is computed, not editable. If
total bill > NTE the line turns red and an inline warning calls it
out — Daryl needs to bring the markup or a cost down.

- The percentage input is pre-filled with the trade default, but
  fully editable — Daryl can override per invoice.
- The "Suggested: 85% (Commercial Door Repair)" attribution makes
  it clear *why* this number, so Daryl trusts (or distrusts) the
  suggestion explicitly.
- If no default exists for the trade, the suggestion line reads
  "No default set — set one in Settings" with a link, and the
  input starts empty.
- The actual % Daryl ends up using is what gets saved to the
  invoice row.

#### What we are explicitly NOT building in v1

- **Per-vendor markup overrides.** Premature without data on
  whether Daryl actually thinks "I always pay Larry more" or just
  "doors get more, and Larry does doors."
- **Per-client markup overrides.** Same reason.
- **AI-suggested markup based on history.** Phase 4.
- **Auto-applying the markup.** Suggestion only. Daryl approves
  every invoice; we don't sneak numbers past him.
- **Migrating the SC-catalog `DOORS` and Brenk's `Commercial Door
  Repair` into one canonical trade.** They coexist today; once
  Daryl tells us he never uses one, we can deprecate.

#### Iteration plan

Once Daryl has used this on, say, a dozen real invoices, ask:

- Is the per-trade default actually matching what you ended up
  choosing? (If not consistently, the model is wrong — maybe it
  really IS per-vendor.)
- Is the suggested vs actual gap concentrated by trade? By vendor?
  By job size? (Data will tell us where conditional rules earn
  their keep.)
- Are you bothered by the suggestion appearing for every job? (If
  it's noise, we'd want to suppress it when Daryl has clearly
  developed a different pattern.)

### Open questions for the next session

- Does Charles have an existing vendor list to import, or start
  empty? *(Answered May 18 — Daryl shared his contact list. Done.)*
- ~~How does Daryl want to express his markup-board rules?~~
  *(Answered May 21 — see "Markup Helper Design" above.)*
- ~~Should the trades picker visually group Brenk-custom vs
  SC-catalog trades?~~ *(Answered May 21 — mix alphabetically.)*
- Color-coding pink/yellow/orange/green for SC stages — should we
  match SC's exact shades, or use cleaner Tailwind colors that map to
  the same conceptual stage?

## Storefront / Dashboard Boundary

The same Next.js project serves **two distinct surfaces** on two
hosts; `proxy.ts` enforces the split before any page renders.

| Host | What renders | Auth required? |
|---|---|---|
| `brenkfacilityservices.com` (apex) | Public storefront — `/marketing/*` route group | No |
| `www.brenkfacilityservices.com` | Same as apex (same `isStorefrontHost` rule) | No |
| `app.brenkfacilityservices.com` | Dashboard — everything in `(app)` route group | Yes (Supabase JWT) |
| `localhost` / `127.0.0.1` | Dashboard. Preview the storefront at `/marketing` directly. | Yes |

**How the isolation actually works:**

1. **Bare-domain rewrite** (`proxy.ts`): if the incoming `Host`
   header doesn't start with `app.` (and isn't `localhost`), every
   path except `/marketing/*`, `/api/*`, `/_next/*`, `/robots.txt`,
   `/sitemap.xml`, and `/favicon.ico` gets rewritten under
   `/marketing<path>`. So `brenkfacilityservices.com/work-orders`
   resolves internally to `/marketing/work-orders`, which doesn't
   exist as a route → clean 404.
2. **Dashboard auth gate** (`proxy.ts`): on the `app.*` host, every
   path except `/login`, `/auth/*`, and the public crawler files
   redirects to `/login?next=…` when there's no Supabase session.
3. **Cookie scoping**: Supabase session cookies are set on
   `app.brenkfacilityservices.com` — they don't propagate up to
   the bare domain, so a dashboard user visiting the storefront
   doesn't accidentally leak their session there.
4. **No dashboard links in storefront markup**: every `<a>` in
   `app/marketing/page.tsx` is either an anchor (`#section`), `/`
   (root of the storefront), `tel:` / `mailto:`, or runs through
   the `safeHref()` allowlist that strips `javascript:`, `data:`,
   etc.

**robots.txt** (`app/robots.txt/route.ts`) is host-aware:
- Bare domain: `Allow: /` (storefront is meant to be indexed)
- App subdomain: `Disallow: /` (block crawlers from the dashboard)
- `Vary: Host` so edge caches keep separate copies.

**Test cases that pass today** (run via `curl -H "Host: …"`):
- `brenkfacilityservices.com/` → 200 storefront ✓
- `brenkfacilityservices.com/work-orders` → 404 (not a dashboard
  page, just an unknown marketing path)
- `brenkfacilityservices.com/storefront` → 404 (editor not
  reachable from bare domain)
- `brenkfacilityservices.com/login` → 404 (no sign-in form on
  bare domain)
- `app.brenkfacilityservices.com/` (no session) → 307 → `/login`
- `app.brenkfacilityservices.com/login` → 200 sign-in form

If you change `proxy.ts` rewrites or auth-gates, re-run these.

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
- Don't conflate `work_orders.nte` with the vendor cost fields.
  NTE is the **client-side ceiling** (set by SC, public to the
  client); `brenk_labor_cost` and `brenk_material_cost` are **what
  Brenk pays the sub-vendor** (operator-entered, Brenk-confidential,
  never sent to SC). The total bill Daryl invoices the client equals
  `(brenk_labor_cost + brenk_material_cost) × (1 + brenk_markup_percent/100)`
  and must be ≤ NTE. The first cut of the markup helper used NTE as
  the cost basis, which was wrong.
- Don't push `brenk_labor_cost`, `brenk_material_cost`, or
  `brenk_markup_percent` to SC. They're Brenk-internal margin data.
  The only number that ever goes to SC is the final total Daryl
  manually enters into SC's own invoice form.

## Communication With Charles

Charles is the sole engineer and contact. He's working evenings and weekends
around a full-time iOS job and grad school. Sessions are intermittent. When
asking clarifying questions, prefer batched questions over single-question
back-and-forth. Charles tracks his hours for invoicing — when reaching natural
session boundaries, surface a brief summary of what was accomplished so it
can go into the bi-weekly invoice.