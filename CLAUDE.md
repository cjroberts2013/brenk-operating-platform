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
| 1 | Foundation & ServiceChannel Integration | **Live in production (2026-05-27)** |
| 1.5 | SC write-back: invoice push + accept/decline | Not started |
| 2 | QuickBooks Integration & Invoice Automation | Not started |
| 3 | Vendor Communication Automation | Not started |
| 4 | Intelligence & Analytics | Not started |
| 5 | Public-Facing Business Website (CMS-driven) | **v1 shipped in Phase 1** |

### Phase reorder (resolved 2026-05-26)

The storefront was originally planned for Phase 5 but shipped as a
v1 in Phase 1 — same Next.js project, hostname-based routing in
`proxy.ts`, editor at `/storefront` in the dashboard. The "Phase 2
vs Phase 5" question is moot: storefront is live; QuickBooks
(Phase 2) is the next major investment. Phase 1.5 (SC write-back,
including `POST /invoices`) sits between them as a small follow-on
once the SC permissions question is unblocked.

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

**Completed (production deployment, 2026-05-27):**
- Second Supabase project (`Brenk Production`) provisioned, all
  Alembic migrations applied, Procrastinate schema applied
- Prod SC app registered, OAuth credentials configured
- Initial prod sync: 336 work orders + 3,008 notes + trades + clients
  + locations seeded
- Daryl's curated dev vendor rows exported via
  `backend/scripts/export_vendors_for_cutover.py` (Brenk-confidential
  notes preserved) and re-reconciled against prod SC user IDs via
  the email-fallback path in vendor sync — 20 vendors matched
- Storefront content seeded for production
- **Patch**: `classify()` and `stage_filter_clauses()` updated to
  treat `primary_status = "OPEN"` as `pending_acceptance` (production
  SC has 9 OPEN-status WOs the sandbox dataset didn't have, so the
  initial classifier missed them and they were invisible on the
  dashboard). Commit `4fe76ba`.
- **Backend on Fly.io**: `brenk-platform-web` (FastAPI, 2 machines
  in `dfw`, /health green, `release_command = alembic upgrade head`
  auto-applies migrations on every deploy) + `brenk-platform-worker`
  (procrastinate, hourly WO sync registered)
- **Frontend on Vercel**: `brenk-operating-platform` project,
  production env vars set (Supabase URL + anon key + API base URL),
  Deployment Protection disabled
- **DNS at GoDaddy**: A records for apex, www, and app all pointing
  at Vercel anycast `76.76.21.21`. Stale "Parked" sentinel deleted.
  TLS certs issued for all three hostnames.
- **CORS verified end-to-end** — preflight from
  `https://app.brenkfacilityservices.com` against the Fly backend
  returns the right `Access-Control-Allow-Origin` + credentials.

**Completed (Phase 1 refinement, 2026-06-02):**
- **Reports page** (`/reports`): markup/spend analytics, margin
  actual-vs-default by trade + spend by vendor + top-line totals,
  from a DB-free aggregation service (`app/services/reports.py`,
  unit-tested). Empty state until markup data exists.
- **Vendor-notified pipeline milestone**: `brenk_vendor_notified_at`
  on work orders, set from the WO-detail workflow checklist
  ("Mark notified"). Tracks the "assigned but never texted" failure
  mode. Backend mirrors the `paid` action shape.
- **Dev-only sidebar tabs**: Storefront + Reports hidden in
  production (`AppShell.tsx`, gated on `NODE_ENV`); the routes still
  resolve by direct URL in any environment.
- **Storefront "Request a Quote" form** (`/quote`): public form posts
  to `POST /api/v1/storefront/quote`, which emails Daryl via **Resend**
  (`app/services/email.py`). Branded inline-styled HTML + plain-text,
  tap-to-call/reply buttons, timestamp, honeypot; the lead is always
  logged so it survives even if email is down. All "Request a Quote"
  CTAs repointed to `/quote`; `proxy.ts` `STOREFRONT_ROUTES` makes the
  clean URL resolve on every host (including local dev).
- **Storefront contact info**: phone (512) 369-2719 and
  daryl@brenkfacilityservices.com (`components/marketing/data.ts`).
- **Backend lint**: ruff 44 to 0 errors; trades now ordered
  case-insensitively (deterministic across DB collations).

**Quote-email prod to-dos (storefront emails won't send live until):**
- `fly secrets set RESEND_API_KEY=… QUOTE_FROM_EMAIL='Brenk Facility Services <quotes@brenkfacilityservices.com>' QUOTE_TO_EMAIL=daryl@brenkfacilityservices.com -a brenk-platform-web`
- Resend domain `brenkfacilityservices.com` verified (done 2026-06-02);
  sender is `quotes@brenkfacilityservices.com`.
- Set the prod storefront `hero_cta_link` to `/quote` (Storefront
  editor or re-seed; prod DB still has the old anchor).
- Optional: DMARC TXT record at GoDaddy for sender reputation.

**Completed (2026-06-06):**
- **Everything above deployed to prod.** Backend redeployed to Fly
  (`alembic upgrade head` applied the RLS + vendor-notified migrations,
  shipped the reports/quote endpoints); frontend deployed to Vercel
  (storefront, `/about`, `/quote`, reports, dev-only tabs). Quote-email
  prod to-dos resolved: Fly Resend secrets set, prod `hero_cta_link`
  set to `/quote`, sending live to Daryl.
- **Security: Supabase `rls_disabled_in_public` advisor closed.** RLS
  enabled on all public tables via migration (backend role is
  `postgres`/`bypassrls`, so unaffected) AND the Supabase Data API
  disabled on both dev + prod projects (we use a direct Postgres
  connection + FastAPI, never PostgREST). Vercel project Root Directory
  was also set to `frontend` (the git-push build was failing without it).
- **Marketing storefront refinement pass** (all live): real services
  list; new `/about` page (family photo, wired into nav + footer); hero
  uses the rooftop-HVAC photo; logo cloud shows real client logos
  (CubeSmart/Extra Space/Sleep Inn), larger + full-color; stats band
  shows derived years-in-business + 180+ facilities (dropped client
  retention); removed dead/placeholder CTAs and links (View all
  services, All projects, Call the 24/7 line, emergency-response lines,
  Service Areas, Careers, Privacy/Terms); left-aligned the value-props
  header; images consolidated under `frontend/public/images/`.
- Dev-server configs saved to `.claude/launch.json` (frontend +
  backend + worker) for `preview_start`.

Live URLs:
- Dashboard: https://app.brenkfacilityservices.com/
- Storefront: https://brenkfacilityservices.com/ (also `www.`)
- Backend API: https://brenk-platform-web.fly.dev/
- Backend health: https://brenk-platform-web.fly.dev/health

**Not yet done:**
- Junction table for multi-vendor-per-WO (current model is single
  `assigned_vendor_id`; deferred until pipeline funnel surfaces the need)
- Daryl onboarding walk-through — sign him in and watch him use it
- Quote-email prod wiring (Fly secrets + prod `hero_cta_link`) — see
  the "Quote-email prod to-dos" list above

## Tech Stack

- **Language:** Python 3.13
- **Backend:** FastAPI, Pydantic v2, structlog — deployed on Fly.io
  (`brenk-platform-web` + `brenk-platform-worker`, region `dfw`)
- **Database:** Supabase (managed Postgres) — two projects, dev + prod
- **ORM:** SQLAlchemy 2.0 with Alembic migrations
- **Job queue:** Procrastinate (Postgres-backed, no Redis needed)
- **HTTP client:** httpx + tenacity for retries
- **Testing:** pytest + respx
- **Frontend:** Next.js 16 + React 19 + Tailwind 4 — deployed on Vercel
  (`brenk-operating-platform` project)
- **DNS:** GoDaddy (A records to Vercel anycast `76.76.21.21`)
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

Production cutover is done. The dashboard, invoice queue, vendors,
and storefront are all live at `app.brenkfacilityservices.com` /
`brenkfacilityservices.com`. Next chunk is **getting Daryl in front
of it**, then closing out the small Phase 1 polish items, then
deciding between Phase 1.5 (SC invoice push) and Phase 2 (QuickBooks).

### WO detail view refinement (requested 2026-06-06, next UX focus)

The work-order detail page right rail (Workflow checklist + Markup
helper) feels cluttered and the whole view can overwhelm. Goal: make
it easier to follow, surfacing the right thing at the right time.
Collapsible sections are on the table but shouldn't hide the next
action. Suggestions to explore (decide with Charles, ideally validate
with Daryl):

1. **Lead with the single next action.** Derive the current stage and
   show one prominent "Next: assign a sub-vendor" CTA at the top, so
   the user doesn't scan the whole 10-stage checklist to know what to
   do. The full checklist becomes secondary.
2. **Compact the Workflow.** Collapse the SC-auto/no-signal stages
   (Accepted, Dispatch confirmed, Work complete, Closed by store,
   Invoiced, Vendor-on-site) into a one-line summary, and keep only the
   Brenk-actionable stages expanded (assign, notify, ready-to-invoice,
   markup, paid). Or replace the tall vertical list with a compact
   horizontal stepper at the top of the page.
3. **Make the Markup helper context-aware.** Collapse it by default and
   auto-expand only when the WO reaches "ready to invoice." Showing the
   full cost/markup form on a WO nowhere near invoicing is most of the
   clutter.
4. **Collapsible sections** (the requested idea) as the mechanism for
   #2/#3, but paired with smart defaults so the next action is never
   behind a click.
5. **Optional layout shift:** a full-width progress strip at the top +
   a lighter right rail that shows only the contextually-relevant card.

Recommendation: combine 1 + 2 + 3 (prominent next-action, summarized
SC stages, context-aware markup helper); collapsible is a good tool but
lean on smart defaults over manual expand/collapse.

### Vendor notification: context + path to automation (captured 2026-06-06)

Today "Mark notified" is just a timestamp — Daryl texts/calls the
sub-vendor himself, then records it. The next-step card now shows the
vendor's preferred contact method (from the vendor record) to make that
manual reach-out faster. Two follow-ups to move toward Phase 3
(Twilio auto-texting):

- **Reminder: ask Daryl what he actually sends a vendor** when he
  reaches out (WO #, location/store, trade, problem description, access
  notes, NTE?, scheduling?, anything else). If we can pin down a clear,
  constrained message shape, the notify step can be **fully automated**
  (send the text via Twilio on assign/notify, log delivery + reply).
- **Manual "additional context" field on the WO.** A Brenk-internal
  free-text field where Daryl can add context the SC description lacks
  (e.g., gate code, "call the GM first", parking). Useful immediately
  on the detail view, and it becomes part of the auto-message payload
  once Phase 3 automation lands. New column + edit control; mirrors the
  other Brenk-internal WO fields.

1. **Daryl onboarding.** Sit with him, sign him in, watch him use it.
   Goals: confirm the UX matches his mental model, capture the first
   round of "this is wrong" / "this is missing" feedback, get the
   markup helper in front of him on a real invoice. Everything below
   is provisional until this happens — Daryl's reaction may
   re-rank the list.
2. **Markup helper / Settings page.** ✅ **Done (committed).**
   Per-trade default markup % captured in Settings
   (`/settings` → `MarkupDefaultsTable`), suggested (never
   auto-applied) on the WO detail markup helper
   (`components/work-orders/MarkupHelper.tsx`), backed by the
   `PATCH /api/v1/trades/{id}` endpoint. v1 — expect iteration
   after Daryl uses it on real invoices. Full design in the
   "Markup Helper Design" section below.
3. **Sub-contractor → WO assignment mapping.** 🔎 **FOUND the
   source — BLOCKED on auth (2026-05-30).** It is *not* in the
   partner API: `Assignee` is empty across the entire prod WO set,
   and the data isn't on the WO, notes, work activities, or any
   OData collection (full probe in
   `backend/scripts/probe_sc_assignee.py`). Charles captured the SC
   portal's actual network call — the Sub-Contractors tab is served
   by a **separate product, SC Workforce** (GPS/check-in), at
   `GET https://workforce.servicechannel.com/api/manager/technician/{technicianId}/dispatchedWOs`.
   The payload carries the sub→WO assignment **and** on-site GPS
   check-in fields (`IsAccessGranted`, `CheckInOutEvents`,
   `BadgePresentedDate`) — i.e. it would also unlock the "Vendor
   on-site 📍" lifecycle stage we'd written off as no-signal. **But
   our partner-API OAuth token is rejected there (401);** Workforce
   is a different auth realm with its own `technicianId` namespace
   (vendor↔technician join is by the `admin+N@` email we already
   sync). The partner-API endpoint
   `GET /workorders/{id}/techniciansAssigned` is **confirmed dead for
   us** — `504 security-permissions` for our provider account in *both*
   prod and sandbox (subscriber-scoped). So **Workforce is the only
   viable read route**, blocked solely on a server-to-server Workforce
   token — bundle into the Phase 1.5 SC-permissions ask. If unblocked,
   delivers the sub→WO assignment panel AND (via Workforce) the "Vendor
   on-site" GPS stage. Full findings in
   `docs/architecture/servicechannel-api.md` → the 2026-05-30 "FOUND" +
   2026-06-01 confirmation sections.
4. **Junction table for multi-vendor-per-WO.** Today's model is a
   single `assigned_vendor_id`. Daryl sometimes splits one WO across
   two trades (locksmith + electrical, say) — migrate to a
   `wo_vendor_assignments` join table when real usage surfaces the
   need.
5. **Phase 1.5: SC invoice push.** `POST /invoices` endpoint
   confirmed; spike plan + read endpoints (for upfront validation
   and auto-deriving Sent/Approved/Paid state) documented in
   `docs/architecture/servicechannel-api.md` → "Invoice endpoints
   — Phase 1.5 anchor". **Write scope CONFIRMED 2026-06-10** — a
   safe `POST /v3/invoices` probe (bogus WO) returned `400 Invalid
   Tracking Number`, not a permissions error, so our SC account CAN
   submit invoices (sandbox; confirm prod before shipping). The full
   payload schema + CubeSmart's live requirements (resolution
   required, `^\w*$` alphanumeric number, per-WO Standard vs Line
   Item) are captured in the doc's "Spike results — 2026-06-10". The
   submit path is buildable now; the ONLY remaining gate is the
   `/v3/odata/invoices` READ permission for auto-paid status sync
   (still 401). Re-runnable probe:
   `backend/scripts/probe_sc_invoices.py`. **Read-back is solved a
   different way:** since the OData read is blocked, invoice state
   (Open→Approved→Paid→Void) comes via **webhooks**. Build-ready spec
   in `docs/architecture/sc-invoice-webhook-sync.md` (FastAPI receiver
   + Procrastinate worker + schema + `work_orders` integration +
   UI-export backfill). This is the next concrete Phase 1.5 build.
6. **Phase 2: QuickBooks Integration & Invoice Automation.** The
   bigger next investment. Scope: pull/push invoices to QBO so
   Sue's clipboard goes away end-to-end. Not started — kick off
   after Daryl onboarding + Phase 1.5 unblockers resolved.

**Open questions for the next session:**
- Color-coding pink/yellow/orange/green for SC stages — match SC's
  exact shades, or use cleaner Tailwind colors? (Daryl can answer
  on first walk-through.)
- After Daryl uses the markup helper on ~12 real invoices: is the
  per-trade default actually matching his choices, or is the rule
  really per-vendor / per-client?

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

**Resolved (2026-05-27):**
- *Production cutover* — done. Both Fly apps deployed, Vercel
  frontend live, DNS + TLS green on all three hostnames, CORS
  verified end-to-end.
- *OPEN-status WOs missing from dashboard* — patched. `classify()`
  + `stage_filter_clauses()` now route OPEN to `pending_acceptance`
  (matches Daryl's mental model for any pre-acceptance WO).

**Other items still deferred:**
- ~10 pre-existing ruff errors in `config.py`, `migrations/env.py`,
  and the autogenerated initial migration.
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
- **Invoice line items push to SC** — `POST /invoices`. Endpoint +
  full payload schema confirmed, and **write access confirmed
  2026-06-10** (our SC account can POST; the only remaining gate is
  the `/v3/odata/invoices` read for auto-paid sync). Spike plan +
  adjacent read endpoints + CubeSmart's live requirements live in
  `docs/architecture/servicechannel-api.md` → "Invoice endpoints —
  Phase 1.5 anchor" / "Spike results — 2026-06-10". Once shipped,
  replaces the manual "Daryl types the total into SC's invoice form"
  step.
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

**Two Supabase projects, both live:**

- `Brenk Dev` — original project, used for local development. Connection
  strings in `backend/.env`.
- `Brenk Production` — provisioned 2026-05-27. Connection strings in
  `backend/.env.production` (gitignored). Fly backend reads from this via
  `fly secrets`; Vercel frontend reads `NEXT_PUBLIC_SUPABASE_URL` +
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` from Vercel env vars.

**Workflow for schema changes:**

1. Develop against dev: edit models, `alembic revision --autogenerate`,
   `alembic upgrade head`, test locally.
2. Commit the migration.
3. Deploy backend to Fly: `fly deploy --config fly.web.toml --remote-only`.
   The `release_command = "alembic upgrade head"` in `fly.web.toml`
   auto-applies the migration to prod Supabase before the new image
   takes traffic. **No manual prod migration step.**

If you ever bring up a third Supabase project (staging, a customer
fork, etc.), remember the one-time setup beyond Alembic: run
`procrastinate --app=app.workers.app.procrastinate_app schema --apply`
against it before the worker boots. Our Alembic migrations don't cover
Procrastinate's own queue tables.

Supabase's built-in branching feature requires the Pro plan, which we're
not on — manual two-project setup is the pragmatic alternative.

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
- Don't forget `procrastinate schema --apply` when standing up a
  fresh database. Our `alembic upgrade head` migrations cover our
  schema, but Procrastinate maintains its OWN tables + 18 stored
  procedures (`procrastinate_jobs`, `procrastinate_workers`,
  `procrastinate_prune_stalled_workers_v1`, etc.) installed via
  its CLI: `procrastinate --app=app.workers.app.procrastinate_app
  schema --apply`. The worker process crashes with `function
  procrastinate_prune_stalled_workers_v1(double precision) does
  not exist` if you skip it. Worth running once on any fresh
  Supabase project before the worker boots.
- Don't expect procrastinate's `--app` flag to take a colon-
  separated `module:variable` path. It's all dots:
  `app.workers.app.procrastinate_app`. Different from gunicorn /
  uvicorn / most other Python CLIs.
- Don't rely on `pip install -e .` putting `/app` (or the project
  root) on `sys.path` for ALL subprocesses. The PEP 660 editable
  install registers an importlib finder that works for the
  top-level package but doesn't always cover nested sub-packages
  when a separate CLI binary is invoked. Belt-and-suspenders: set
  `PYTHONPATH=/app` (or equivalent) in the runtime env. Our Fly
  configs do this; if you add a third app or change the Dockerfile
  WORKDIR, keep the PYTHONPATH match.

## Communication With Charles

Charles is the sole engineer and contact. He's working evenings and weekends
around a full-time iOS job and grad school. Sessions are intermittent. When
asking clarifying questions, prefer batched questions over single-question
back-and-forth. Charles tracks his hours for invoicing — when reaching natural
session boundaries, surface a brief summary of what was accomplished so it
can go into the bi-weekly invoice.