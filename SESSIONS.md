# SESSIONS.md

Running log of work sessions on the Brenk Operating Platform. Each entry
captures what was accomplished, decisions made, and what's queued up next.
Also serves as backup documentation for bi-weekly invoices.

Format: most recent at the top.

---

## Session: May 25, 2026 (part 2) — ~3 hours

Built Phase 5 v1: a public marketing storefront for
`brenkfacilityservices.com` plus a dashboard editor that lets
Daryl edit every section without touching code. Promoted ahead of
the rest of Phase 5 work because the SC invoice-API stuff is
parked waiting on permissions clarification.

### Accomplishments

**Backend: storefront data model + endpoints.**
- New tables: `storefront_content` (singleton row keyed by id=1,
  every page-level field as nullable columns) and
  `storefront_services` (ordered list).
- Single-row + ordered-list design intentionally kept simple for
  v1. Refactor to block-based or multi-page can come later
  without losing data.
- `GET /api/v1/storefront/` is **public** (no auth). Mounted via a
  new `public_router` alongside the existing `api_router` so the
  JWT-auth dependency chain doesn't apply.
- `PATCH /api/v1/storefront/` and `PUT /api/v1/storefront/services`
  are authenticated. Singleton auto-creates on first GET so a
  fresh database still serves valid JSON.

**Frontend types + API client.**
- New `lib/api/public.ts` with a no-auth fetcher (mirrors
  `apiFetch` but skips the Supabase token attachment). Tagged
  `fetch` with `next: { tags: ['storefront'] }` so the editor's
  save action can call `revalidateTag('storefront', 'max')` and
  immediately bust the public site's cache.
- New `lib/api/storefront.ts` wraps both public and admin variants.

**Dashboard editor at `/storefront`.**
- New sidebar entry (GlobeAltIcon).
- Form-based editor split into seven sections: Hero & Branding,
  About, Service area, Contact, Footer, and Services (separate
  save since it hits a different endpoint).
- Each section has its own dirty-flag + Save button that activates
  only when something's changed. Green "Saved" check on success.
- Services section supports add/remove + up/down reordering via
  arrow buttons. `sort_order` is renumbered monotonically on save.
- "Preview" link in the header opens `/marketing` in a new tab.

**Public storefront at the bare domain.**
- Standalone layout at `app/marketing/layout.tsx` — no AppShell,
  no auth, no Supabase client. Just the marketing page.
- Single-page design with anchored sections: Hero, Services,
  About, Service area, Contact, Footer. Blue palette (Tailwind
  `blue-700` anchor) matching Daryl's brand preference. Hero +
  About support optional images; falls back to a soft gradient
  block when no image is set.
- Family-business voice in the seeded copy ("answer the phone,
  show up on time, treat every property like it's our own").

**Hostname routing in `proxy.ts`.**
- Added a bare-domain rewrite: any request whose host doesn't
  start with `app.` (and isn't localhost) gets rewritten under
  `/marketing/`. So `brenkfacilityservices.com/` serves the
  storefront, `app.brenkfacilityservices.com/` serves the
  dashboard, both from the same Next.js project.
- `/marketing` added to `PUBLIC_PATH_PREFIXES` so the proxy's
  auth check doesn't redirect to `/login`.
- Local dev: storefront previewed at
  `localhost:3000/marketing`; dashboard at `localhost:3000/`.

**Seeded initial content.**
- New `scripts/seed_storefront.py` writes Brenk-appropriate
  starter copy: hero pitch, family-business about paragraph,
  service-area body covering the I-35 corridor, contact info
  pulled from Daryl's existing details, and six service cards
  (Plumbing, Electrical, Doors & Gates, Painting & Drywall,
  Flooring, General Building) with Heroicon mappings.
- Idempotent — re-running resets to known defaults rather than
  duplicating.

### Decisions & Observations

- **One Next.js project, hostname routing.** CLAUDE.md leaned
  "probably two separate projects" for caching cleanliness, but
  for v1 the single-project + proxy.ts rewrite is materially
  simpler and lets us share the existing Supabase auth helpers.
  Cookie scoping still works correctly because dashboard cookies
  live on `app.<domain>` and don't leak to the bare domain. If
  build sizes or caching strategies diverge enough later we can
  split — no data migration required, just a `next` config move.
- **Singleton page model over block-based.** A "real" CMS would
  let Daryl drag-and-drop block components. We don't need that.
  Brenk has one marketing page, fixed structure. Form-based
  editor ships in a day vs a week of block-system work, and
  re-modeling later doesn't lose any data.
- **Image uploads deferred to v1.1.** The editor accepts image
  URLs as text inputs for now. Daryl can host on his existing
  GoDaddy hosting / Imgur / wherever and paste a URL. Saves us
  wiring Supabase Storage + CORS + a file-upload widget for v1.
  Add when Daryl actually has photos he wants to manage.
- **`revalidateTag` now requires a second arg in Next 16.** The
  deprecation warning surfaced when type-checking; pass `'max'`
  as the second arg or migrate to `updateTag`. Worth a mental
  flag for any other revalidate calls we add later.
- **Voice over correctness.** Seeded copy intentionally says
  things like "for years" rather than a specific decade, and
  refers to "Daryl Brenk" / "our family". Daryl can refine the
  specifics once he proofs it — the goal of v1 copy is to give
  the storefront a face that isn't `Lorem ipsum`.

### Up Next

The two clean next moves remain unchanged:

1. **Production cutover.** New Supabase project on your side,
   `alembic upgrade head`, seed scripts (including the new
   storefront seed), deploy backend to Fly.io, deploy frontend
   to Vercel, DNS for both `brenkfacilityservices.com` (apex →
   Vercel) and `app.brenkfacilityservices.com` (CNAME → Vercel).
2. **Phase 1.5 invoice push to SC.** Spec fully documented;
   actual build can start any time. Webhook receiver buildable
   in dev against fixtures; registration needs the production
   public URL.

Either order works. Storefront can be live + Daryl can be
editing copy while we wait on the SC permissions sort-out.

### Deferred / known v1.1

- Image upload to Supabase Storage (currently URL-only inputs).
- Storefront preview link in the editor opens
  `localhost:3000/marketing` even after deploy — should detect
  prod and open the real bare-domain URL.
- The "Reports" sidebar entry is still a placeholder. Whenever
  we get to Phase 4 analytics, the storefront's `default_markup`
  + invoice paid history becomes a real spend-tracking surface.

---

## Session: May 25, 2026 — ~5 hours

Built the Invoice Queue — Sue's-clipboard replacement. Four-tab page,
per-tab helper text, markup helper card on WO detail, Settings page
gets a markup-defaults table, and the data model now captures
vendor cost as labor + material separately so Phase 4 analytics can
ask where the money's going. Also confirmed the SC Invoice API
surface for the Phase 1.5 write-back work.

### Accomplishments

**Backend: invoice-queue data model + endpoints.**
- New columns on `trades`: `default_markup_percent` (suggested,
  never auto-applied).
- New columns on `work_orders`: `brenk_labor_cost`,
  `brenk_material_cost`, `brenk_markup_percent`, `brenk_marked_up_at`,
  `brenk_paid_at`. All **Brenk-confidential** — privacy boundary
  documented in the model docstring + `CLAUDE.md` "Things To Avoid"
  + the per-field comments in the Pydantic schemas.
- PATCH `/api/v1/work-orders/{id}` accepts these new fields. Setting
  markup auto-stamps `brenk_marked_up_at` on first set; subsequent
  edits leave the original moment alone. `paid: "now"` / `"clear"`
  toggles `brenk_paid_at`.
- PATCH `/api/v1/trades/{id}` lets Settings edit the per-trade
  default markup %.
- `?invoice_tab=…` filter on the WO list endpoint. Four tabs:
  `ready_to_markup`, `marked_up`, `sent`, `paid`. Composite filters
  share the source-of-truth stage clauses from `pipeline.py`.

**Three different money numbers — keep them straight.**
- This earned its own table in CLAUDE.md after the first cut of the
  markup helper auto-pulled NTE as the cost basis. NTE is the
  client-side ceiling (set by SC, visible to client); the vendor
  costs are what Brenk pays the sub (operator-entered, never sent
  to SC); markup is Brenk's margin on top. Total bill = (labor +
  material) × (1 + markup/100), must be ≤ NTE.

**Labor + material split.**
- Originally added `brenk_vendor_cost` as one number. Charles asked
  for labor and materials tracked separately so Phase 4 analytics
  can slice spend by category. Replaced with `brenk_labor_cost`
  and `brenk_material_cost` (rolled back the original migration in
  dev, generated a fresh one — never committed the stale shape).
  Subtotal is computed, not stored.

**Frontend: /invoices page.**
- Four tabs with live counts in the nav. Per-tab columns adapt to
  the workflow (no markup column on "Ready to mark up"; total bill
  + sent date on "Sent"; just paid date on "Paid").
- Per-tab helper banner explains in plain English what's in the
  tab and what action moves a row forward.
- "Vendor cost" column shows labor + material summed; falls back
  to "Awaiting vendor bill" when nothing's been entered yet.

**Frontend: Markup helper card on WO detail.**
- Right-rail card. NTE shown read-only as a ceiling reference.
  Labor cost + material cost as separate inputs. Computed
  subtotal. Markup % with attribution to the trade default if any.
  Live total-bill calculation that turns red and shows an inline
  warning if it exceeds NTE.
- Privacy reminder banner at the top: "Vendor costs and markup
  stay private to Brenk; never sent to ServiceChannel."
- Single Save button covers all three inputs. Clear-markup button
  appears only when there's a saved markup (returns the WO to
  "Ready to mark up" without losing vendor costs).
- Mark paid / Undo controls in a separate band below.

**Frontend: Settings → Default markup by trade.**
- Inline-editable table of all trades + their default %. Save
  button activates only when dirty. Enter key also saves. Brenk-
  custom trades get a small tag so Daryl can see which labels
  come from him vs SC. Info banner shows X-of-Y coverage.

**Sidebar: new "Invoices" entry** (BanknotesIcon).

**SC API discovery (Phase 1.5 anchor).**
- Charles shared the SC Swagger UI list for the Invoices group.
  Captured the relevant endpoints in
  `docs/architecture/servicechannel-api.md` → "Invoice endpoints —
  Phase 1.5 anchor": `POST /invoices` exists, plus an
  `InvoiceRequirements` GET for upfront validation, an
  `InvoiceRejectionReasons` GET for failure context, and an
  `/odata/invoices` list endpoint that may let us auto-derive
  "Sent → Approved → Paid" status (replacing the manual Mark paid
  button). PUT reject/onhold/approve are client-side — we observe,
  don't call. Documented the spike plan for when Phase 1.5 starts.

### Decisions & Observations

- **One source of truth for stage definitions** (continued from
  previous session). The invoice-queue tabs use the same
  `stage_filter_clauses` from `app/services/pipeline.py` that the
  dashboard uses for counting. Tab counts and list page row counts
  are guaranteed to match by construction.
- **NTE is sacred.** First cut of the markup helper used NTE as
  the cost basis for markup, which is wrong — NTE is the ceiling,
  not the cost. Caught by Charles immediately. Now documented in
  CLAUDE.md with a three-row table and a "Things To Avoid" rule.
- **Vendor cost = labor + material, split at entry time.** Could
  have stored one combined number and split later if needed, but
  splitting at entry preserves the breakdown Phase 4 analytics
  will want. The subtotal is computed; the two columns are the
  source of truth.
- **Markup helper is intentionally not auto-applied.** Even when
  a trade has a default, the input is pre-filled but Daryl still
  has to hit Save. The "Markup Helper Design" section of CLAUDE.md
  spells out why — Daryl approves every invoice, we don't sneak
  numbers past him.
- **Brenk-confidential fields are surfaced in three places now:**
  the model docstring, the Pydantic schema field comments, and a
  "Things To Avoid" rule. If anyone ever wires SC submission, the
  warning is impossible to miss.
- **Phase 1.5 (invoice push to SC) is no longer speculative.** The
  endpoint exists (`POST /invoices`). The next step there is an
  API spike, not exploratory research.

### Up Next

The two "directly attack Daryl's failure modes" pages are now both
live — Dashboard funnel (last session) + Invoice queue (this one).
Remaining Phase 1 chunks:

1. **SC employee → WO assignment research** (paired with prod
   cutover).
2. **Multi-vendor-per-WO junction table** — when the funnel
   surfaces the need.
3. **Production cutover** — export script + email-fallback ready;
   second free-tier Supabase project, alembic upgrade, seed from
   prod SC, click Sync.
4. **Phase 1.5: invoice push to SC** via `POST /invoices`. Spike
   plan documented; ready to start whenever Charles wants the
   manual SC-entry step removed.

### Open questions

- Auto-submit invoices to SC, or click-to-prefill (open SC's form
  with values populated, Daryl reviews + clicks Submit himself)?
  Click-to-prefill keeps Daryl's final review beat; auto-submit
  removes more friction. Decision deferred to Phase 1.5 kickoff.

---

## Session: May 21, 2026 (part 2) — ~2.5 hours

Built v1 of the Dashboard pipeline funnel — Daryl's at-a-glance read
on where the business stands today.

### Accomplishments

**Backend: pipeline stage logic + endpoint.**
- New `backend/app/services/pipeline.py` is the single source of
  truth for what defines each lifecycle stage. Holds the `StAGES`
  tuple (key, label, color, icon, stuck-threshold), a Python
  `classify()` for the dashboard's count-and-classify pass, and a
  matching `stage_filter_clauses()` returning the SQLAlchemy WHERE
  clauses for the WO list endpoint. Both must stay in sync so a
  tile's count equals the list page's row count for any stage.
- New `GET /api/v1/dashboard/pipeline` (in
  `backend/app/api/v1/endpoints/dashboard.py`) returns the full
  payload: per-stage counts + avg age + stuck count, the top 20
  most-overdue WOs ("Stuck right now" panel), and the top-line
  open vs invoiced split. Loads every WO with refs eagerly, then
  classifies + aggregates in Python — at ~341 rows total this is
  trivially fast and keeps the stage logic in one place.

**Backend: `?stage=` query param on the WO list endpoint.**
- `GET /api/v1/work-orders/?stage=<key>` applies the same composite
  filter the dashboard uses for counting. Verified end-to-end:
  every tile's count agrees byte-for-byte with the list page's
  `total` for that stage (9 / 46 / 12 / 23 / 229).
- Unknown stage key returns a clean 422 with the list of valid
  keys — better than silently falling through to "all WOs".

**Frontend: Dashboard home page (`/`).**
- Replaced the placeholder with header (open + invoiced counts),
  row of five pipeline tiles (mobile 2-up, md 3-up, xl 5-up), and
  a "Stuck right now" panel underneath. Tiles use SC's color
  language and link directly to the WO list pre-filtered by stage.
- `PipelineStageTile` renders a colored accent bar, optional icon
  (user / money / check), big count, avg-age line, and a red
  "X stuck" callout when stuck_count > 0 (or quiet "on track").
- `StuckPanel` renders the top-20 most-overdue WOs as a tight
  table — status badge, WO#, stage, location, trade, vendor (or
  "Unassigned" in red), how-overdue, last-SC-update.

**Stage-filter chip on the WO list page.**
- When you land via a tile click, an `Active filter: Stage:
  <label> ×` chip appears below the header. One click clears the
  stage filter and drops the page back to the full list (preserving
  any unrelated `q=` or `status=` params already in the URL, but
  resetting pagination since the result set just got bigger).

**Merged Dispatched + Vendor-assigned tiles.**
- Original plan had them as separate stages, but in Daryl's actual
  workflow accepting an SC dispatch and texting the sub-vendor
  happen in the same sitting — splitting them created a "stage"
  he never operationally occupies. Now one "Dispatched" tile with
  the 👤 icon as a quiet reminder that vendor assignment lives
  inside this stage. When Twilio lands in Phase 3 ("vendor
  notified" becomes a meaningful timestamp distinct from "vendor
  assigned"), we re-introduce the split.
- The `classify()` function still accepts a `has_vendor` argument
  for forward-compat, but ignores it for now. Inline comment +
  module docstring document the merger so the rationale isn't
  lost.

### Decisions & Observations

- **Single source of truth for stage definitions** — Python
  `classify()` for the dashboard count pass, `stage_filter_clauses()`
  for the WO list SQL filter. Both live in
  `app/services/pipeline.py`, both consult the same `STAGES`
  tuple, both **must stay in sync**. The module docstring flags
  this. The smoke test (dashboard count == list page total for
  every stage) catches drift in one shot.
- **`?stage=…` over `?extended=…`+`?has_vendor=…`.** Considered
  exposing the raw SC fields as separate filter params, but that
  would put the stage-composition knowledge in the frontend AND
  the backend. One stage param is cleaner: the dashboard
  generates the URL, the list endpoint runs the filter, the
  definition lives once.
- **Cancelled / no-charge WOs are excluded from the pipeline.**
  22 of them in the dataset. They're terminal — Daryl doesn't
  need to act on them — so they don't appear on a tile or get
  counted in `total_open` or `total_invoiced`. Visible in the WO
  list directly if Daryl ever wants to find one.
- **"Age in stage" uses `sc_updated_date` as a proxy.** Not
  perfect (Brenk-side actions in our app don't bump it), but
  cheap and good enough for v1. When we add Brenk-internal stage
  flags (vendor_notified, ready_to_invoice, markup_decided) with
  their own timestamps, we'll switch the age computation to the
  per-stage timestamp.
- **Stuck thresholds are hard-coded per stage** (1 / 3 / 7 / 3
  days; invoiced has none). One-line tweaks in pipeline.py if
  Daryl tells us "1 day is too aggressive for pending acceptance,
  give me 3." Configurable-from-Settings is overkill for v1.
- **The sandbox dataset is old.** Most WOs haven't been touched
  in 50+ days, so nearly everything reads as "stuck" in the
  current view. That's expected — once we're on fresh prod data,
  the stuck count will be a much smaller, actionable number.

### Up Next

The dashboard funnel was the first of the "two pages that directly
attack Daryl's failure modes." Next chunk is the **Invoice queue**
— Sue's-clipboard replacement.

Per the markup design captured earlier today:

1. Migration to add `default_markup_percent` to `trades` and
   `brenk_markup_percent` + `brenk_marked_up_at` (+ optionally
   `brenk_paid_at`) to `work_orders`. Cheap nullable columns.
2. PATCH endpoints to set the markup % on a WO + the default %
   on a trade.
3. New `/invoices` page with the four tabs Sue actually thinks in
   ("Ready to mark up" / "Marked up, ready to send" / "Sent" /
   "Paid"). Tab content is just a filtered WO list with the
   markup helper inline.
4. Settings page gets a markup-defaults table.

Then in following sessions: SC employee→WO research, the
multi-vendor junction table when the funnel surfaces a need,
production cutover.

### Cleanup notes

- A spawned follow-up task ("Add ?extended= filter to WO list
  page") is now obsolete — the cleaner `?stage=` approach
  supersedes it. Dismiss the chip in the UI.

---

## Session: May 21, 2026 — ~30 min (docs only)

Short docs-only checkpoint. Resolved two open questions and captured
one new research item.

### Decisions captured

- **Markup-board rule shape:** per-trade default markup % on the
  `trades` table, suggested (never auto-applied) on the invoice
  detail with a manual override input. Settings page exposes an
  inline-editable table of all trades + defaults + free-text notes.
  Daryl currently does the math in his head, so v1 is a starting
  point — we'll iterate once he tells us what's actually missing.
  Full design captured in CLAUDE.md → "Markup Helper Design (v1)".
- **Trades-picker grouping:** mix Brenk-custom and SC-catalog trades
  together alphabetically, no visual separation. The picker is just
  there to identify the right vendor; the origin of the label is
  irrelevant. Already this way in the form modal — no work needed.

### Research item added

Daryl pointed out that the SC web UI exposes per-employee work-order
assignments. Our May 19 probe found the per-WO `Assignee` field empty
across all 341 sandbox WOs, but that's likely a sandbox-only
condition. New section in `docs/architecture/servicechannel-api.md`
lists the next probes to run (OData `$expand`, filter syntax, web-UI
network-tab inspection) and the integration shape if we find it —
a "Tech-assigned in SC" panel on the vendor detail page,
read-only, cross-referenced against our Brenk-native assignment.

### Up Next

Unchanged from the May 20-21 plan. With the markup design captured,
the **Invoice queue** is no longer blocked on a Daryl decision — we
can build the v1 surface and iterate. Recommended order:

1. Dashboard pipeline funnel.
2. Invoice queue (now unblocked by the markup design).
3. SC employee→WO research (paired with the prod cutover).
4. Multi-vendor-per-WO junction (when the funnel surfaces the need).
5. Production cutover.

---

## Session: May 20–21, 2026 — ~3 hours

Polish session on the Work Orders + Vendors views: dial back the SC
sync cadence, add a manual "Sync now" trigger + last-synced status
line, and wire the dashboard's top-bar search up to real list-page
filtering.

### Accomplishments

**Sync cadence: every 5 min → hourly.**
- `backend/app/workers/tasks.py`: changed
  `@procrastinate_app.periodic(cron="*/5 * * * *")` to
  `cron="0 * * * *"`. Comment in-file explains the math (Brenk gets
  ~8 WOs/day; 288 polls/day was massively over-spec; 24/day is friendly
  to monthly network-call budgets and well under any SC throttle).
- Configurable later by editing one line if Daryl's response time on
  new WOs becomes a real concern.

**Manual sync + last-synced display on `/work-orders`.**
- Backend: `GET /api/v1/work-orders/sync-status` returns
  `{ last_synced_at: datetime | null, work_order_count: int }`, derived
  from `MAX(work_orders.last_synced_at)`. Cheap single query.
- Backend: `POST /api/v1/work-orders/sync` runs the orchestrator
  inline so the response carries `{fetched, upserted, notes_synced,
  errors}`. Idempotent — same upserter as the periodic sync.
- Route order matters: both new routes are registered above
  `/{work_order_id}` so `sync-status` doesn't get matched as a
  path param ("Input should be a valid integer, unable to parse
  string as an integer" — see Decisions below).
- Frontend `components/work-orders/SyncWorkOrdersButton.tsx`:
  client component with `useTransition`, spinning icon while pending,
  and a status-line companion that flips between four states —
  *Last synced X minutes ago · auto-syncs every hour* /
  *Pulling latest from ServiceChannel…* / *Synced 341 work orders ·
  3 notes refreshed* / *Sync failed: …* — depending on whether a
  manual run is in flight, just completed, or errored. Server action
  `syncWorkOrdersAction` revalidates `/work-orders` after.
- WO list page now fires `listWorkOrders` and `getWorkOrderSyncStatus`
  in parallel via `Promise.all` so the extra endpoint is free
  latency-wise.

**Contextual top-bar search.**
- New `components/ContextualSearch.tsx` replaces the dead Tailwind UI
  search placeholder in the AppShell. Behavior:
  - On `/work-orders` → placeholder *"Search work orders by #,
    location, problem, caller…"*. Backend matches `sc_number`,
    `sc_purchase_number`, `problem_code`, `caller`, `description`,
    `location.store_id`, `location.name`, `client.name`,
    `client.short_name`.
  - On `/vendors` → *"Search vendors by name, phone, email, area,
    trade…"*. Backend matches `name`, `phone`, `email`,
    `service_area`, and the vendor's specialized trade names (via
    a subquery so a multi-trade vendor doesn't duplicate rows).
  - Other paths → search is hidden behind an invisible spacer so
    the bell + user menu don't hop around.
- 200ms keystroke debounce → `router.replace('?q=…')`. `replace` not
  `push` so backspacing through 8 characters doesn't litter 8
  entries in the back stack. Pagination resets when the search
  changes.
- URL-driven (`?q=…`), so refresh / back-forward / paste-link all
  work. Server components read `searchParams.q` and re-fetch.
- An ✕ icon appears once you've typed anything — one click clears.
- Backend: added `q` query param to `GET /api/v1/work-orders/` and
  `GET /api/v1/vendors/`. `ILIKE` for case-insensitive substring
  (Postgres handles case folding natively — no `LOWER()` round-trip).
- Verified search counts against live dev DB: `"plumb"` → 18 WOs,
  `"350200"` → 1 WO by number, `"austin"` → 10 vendors,
  `"512"` → 7 vendors by phone area code.

**Race-condition fix in the search input.**
- First cut of `ContextualSearch` would drop trailing characters
  when typing fast: the debounce push would land an intermediate
  URL while the user kept typing, then the resync-from-URL effect
  would clobber the local input with the stale URL value.
- Fix: track `lastPushedRef` (the last value WE pushed), and have
  the resync effect skip when the incoming `urlValue` matches it.
  External URL changes (pathname change, paste, back/forward) still
  flow through because their value won't match the ref.

**Better error surfacing in `lib/api/server.ts`.**
- The original `apiFetch` only handled `detail` strings on error
  bodies. FastAPI validation errors arrive as
  `{detail: [{loc, msg, type}, …]}` — an array — so the old code
  silently fell back to `"422 Unprocessable Content"` (just the
  status text), hiding the real field-level reason.
- Now flattens validation arrays into a readable
  `query.q: Input should be a valid string` line, AND
  `console.error`s the URL + status + detail on the server side
  so dev-time failures are loud.
- This caught the missing-`service_area` field-passthrough bug
  the very next time it would have happened (see below).

**`service_area` field-passthrough bug.**
- Previous session added `service_area` to `VendorSummary` and
  `VendorDetail` Pydantic schemas but missed two manual constructor
  calls in `_to_summary` and `_to_detail` (`backend/app/api/v1/
  endpoints/vendors.py`). Every call to `/api/v1/vendors/` returned
  a Pydantic ValidationError during response construction.
- The WO detail page calls `listVendors(...)` for its assignment
  picker, so navigating to a WO crashed the page. The improved
  error surfacing made the failing field obvious in one shot.
- Fix: pass `service_area=vendor.service_area` in both helpers.
  WO endpoints already use `WorkOrderDetail.model_validate(wo)`
  (auto-picks new fields via `from_attributes=True`), which is the
  safer pattern. The vendors endpoint is worth migrating to the
  same pattern at some point.

**Local dev gotcha caught + documented.**
- Symptom: `[apiFetch] GET /api/v1/work-orders/sync-status → 422:
  path.work_order_id: Input should be a valid integer, unable to
  parse string as an integer.` Meaning: FastAPI tried to parse
  `"sync-status"` as the `{work_order_id}` int.
- Cause: uvicorn was running without `--reload`, so it never picked
  up the new route declarations after the file edits. The new
  literal `/sync-status` route was on disk but not in memory — the
  request fell through to `/{work_order_id}`.
- Fix: restarted uvicorn with `--reload`. Confirmed via the live
  `/openapi.json` that the new routes registered correctly.

### Decisions & Observations

- **Hourly cron is the right floor for now.** SC's API doesn't
  surface change-data-capture (no `updatedSince` we trust), so we
  have to full-scan to catch new WOs. Every 5 min was burning
  network and SC throttle budget for no operator benefit — Daryl
  doesn't refresh that often anyway, and the manual "Sync now"
  button handles the urgent-pull case.
- **Route ordering still matters in FastAPI.** Literal routes need
  to register above `/{param}` routes to avoid being swallowed by
  path-param matching. Worth flagging in any future endpoint that
  adds a sibling literal under a `{id}`-suffixed router.
- **Contextual search > global search at this scale.** Considered a
  global search-everything box, but on every list page the user is
  really asking "narrow this list to what I care about," not "where
  is this thing in the system." Contextual maps to that directly,
  re-uses the existing `?q=` URL contract, and needs no new results
  page. If Cmd+K-style global ever becomes necessary, it'd live
  alongside as a separate affordance.
- **`useTransition` around `router.replace` is the recommended
  pattern,** but it's NOT what kept the input responsive during
  fast typing — the input is controlled by local state via direct
  `setValue` on `onChange`, which is high-priority and untouched
  by the transition. The fast-typing bug was a state-overwrite
  race, not an input-lag issue.
- **Pydantic manual-constructor pattern is fragile.** Any time you
  add a required field to a schema, every manual `Schema(...)`
  constructor in the codebase needs updating in lock-step. Using
  `Schema.model_validate(orm_obj)` with `from_attributes=True`
  auto-picks new fields and is the safer pattern. Migrate the
  vendors endpoint when we touch it next.
- **Run uvicorn with `--reload` in dev.** Already documented in
  `docs/runbooks/local-development.md`, but worth saying again
  here — without it, every backend edit silently does nothing
  until a manual restart, and the failure mode is exotic (FastAPI
  matching against the OLD routing table while you stare at the
  NEW source on disk).
- **Surface API error details aggressively in dev.** The
  `console.error` in `apiFetch` means the dev terminal now logs
  every backend 4xx/5xx with the actual reason — no more
  guessing what FastAPI is complaining about from a generic
  status-text fallback.

### Up Next

Unchanged from the May 19 plan — the search + manual sync were
polish work that fits between the Vendors-page completion and the
Dashboard funnel. Next chunk is still:

1. **Dashboard pipeline funnel** (replaces the placeholder home).
2. **Invoice queue** (Sue's-clipboard replacement).
3. **Markup helper / Settings page** (blocked on Daryl input on the
   markup-board rule shape).
4. **Multi-vendor-per-WO junction table** (when the funnel surfaces
   the need).
5. **Production cutover** (export script + email-fallback are ready).

### Open questions still on the table

- Markup-board rule shape (per-trade %, per-vendor %, free-text,
  reference card?). Blocks the invoice queue.
- Trades-picker grouping: Brenk-custom vs SC-catalog side-by-side
  alphabetical, or grouped sections? Defer until Daryl uses it.

---

## Session: May 19, 2026 — ~5 hours

Closed the loop between SC's user list and Brenk's vendor records,
captured Daryl's real vendor contact data into dev with his preferred
labels, and added a service-area dimension so we can route work by
geography.

### Accomplishments

**Vendor sync from SC (commits coming in this session):**
- Investigated where SC stores the "assigned tech / vendor" idea.
  Probed `/v3/odata/employees`, `/v3/odata/users`, `/v3/workorders/{id}`
  Assignee field, and `/v3/workorders/{id}/workactivities`. Conclusion:
  SC's sandbox doesn't expose a usable per-WO vendor identity through
  v3 — the Assignee field is empty across our 341 WOs and the only
  user-level data we can pull is the OData users endpoint. Decision:
  **stay with the Brenk-native assignment model** (already shipped on
  WO detail) and use SC's `users` list purely as a seed for vendor
  identities.
- New SC client method `list_users()` hitting
  `/v3/odata/users?$select=Id,FullName,Email,UserName,UserType,Disabled`.
  (Plain `/v3/users` returns 401 — OData is the only path.)
- New `app/services/sync/vendors.py` with `sync_vendors_from_sc`:
  - **Match strategy 1:** existing row by `sc_user_id`
  - **Match strategy 2:** existing row by lower(email) — covers the
    sandbox → production cutover where the same human gets a different
    SC user id but keeps their email. Critical so Daryl's curated
    notes survive the environment swap.
  - Otherwise insert a new row.
  - Brenk-internal fields (markup_notes, payment_terms,
    contact_preference, communication_notes, mobile_app_capable,
    trade_specializations, notes, is_active) are **never overwritten**
    by sync. Daryl owns those columns.
- New `vendors.sc_user_id` column (nullable, unique, indexed). NULL =
  Brenk-only vendor that never came from SC.
- `POST /api/v1/vendors/sync` endpoint + Procrastinate `sync_vendors`
  task body (was a stub).
- Frontend: new `SyncFromScButton` client component with
  `useTransition`, server action `syncVendorsAction`, wired into the
  Vendors page header next to "Add vendor". Shows the
  fetched/created/updated/errors summary inline after a sync.

**Daryl's real vendor data captured into dev:**
- Daryl sent over contact info (phone, email, contact preference,
  payment terms) and trade specializations for 12 of his real
  sub-vendors. All 12 already existed as synthetic
  `admin+N@brenkfacilityservices.com` rows from the prior SC sync —
  matched them by id and filled in real data.
- New idempotent `scripts/seed_daryl_vendor_contacts.py` is the
  authoritative record of how the data was applied. Safe to re-run.

**`vendors.service_area` column added:**
- Daryl asked us to track geographic reach. Brenk services the Austin
  + San Antonio corridor; some vendors travel anywhere, some are
  locked to a specific area (OH Door Longview = Longview only). New
  nullable text column captures the free-text answer.
- Alembic migration, model, Pydantic schemas, frontend types,
  VendorFormModal input (paired with Payment terms in a 2-col row),
  Vendors table column, vendor detail Profile field. Seeded all 12 of
  Daryl's vendors with their area.

**Daryl's trade vocabulary now lives alongside SC's:**
- Daryl writes "Plumber" not "PLUMBING", "Window and Glass Repair" not
  "WINDOWS/GLASS". Created 17 Brenk-custom trades (sc_trade_id NULL)
  matching his exact phrasing in Title Case, and reassigned every one
  of his 12 vendors to those. The SC catalog trades (PLUMBING,
  ELECTRICAL, etc.) stay around for future work-order auto-tagging.
- Three custom trades created in an earlier seed pass (WINDOWS/GLASS,
  BACKFLOW, DRYWALL) were renamed in place to their Daryl-labeled
  equivalents so we don't leave orphan rows in the trades picker.

**Sandbox → production cutover prep:**
- New `scripts/export_vendors_for_cutover.py` dumps every vendor row
  + their trade specializations + Brenk-only custom trades as a single
  portable SQL script. Pipe to `psql "$PROD_DATABASE_URL" < vendors.sql`
  at cutover, then click "Sync from ServiceChannel" — the email-
  fallback in the sync service reconciles each row to its production
  SC user id without losing Daryl's curated notes.
- The export excludes environment-local columns (id, sc_user_id,
  sc_provider_id, raw_data, created_at, updated_at). Vendors with
  trades use a `WITH new_vendor AS (... RETURNING id) INSERT INTO
  vendor_trades ...` CTE so the script doesn't depend on prod's trade
  ids matching dev's. Custom trades use
  `INSERT ... ON CONFLICT (name) DO NOTHING` for re-run safety.

**Dev-env IPv4 fix:**
- After a backend restart mid-session, Work Orders page broke with
  `fetch failed → ECONNREFUSED`. Cause: Node's undici resolves
  `localhost` to `::1` (IPv6) first but uvicorn binds to IPv4 only.
- Pinned `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in `.env.local`
  and documented the trap in `.env.local.example`.

**LICENSE cleanup:**
- Resolved a stale `<<<<<<< HEAD` merge marker block in LICENSE.
  Kept the proprietary text (deleted the MIT alternative). The file
  is now clean.

### Decisions & Observations

- **No more probing SC for assignment data.** v3 doesn't expose it.
  The Brenk-native `work_orders.assigned_vendor_id` is the only
  source of truth going forward; SC users are *just identity seeds.*
- **Email-fallback is load-bearing for prod cutover.** Without it,
  Daryl's curated notes/markup/payment-terms would be stranded on
  dev rows when the production SC sync invents fresh `sc_user_id`s
  for the same people. The export script + email-fallback together
  make the sandbox-to-prod migration low-risk.
- **Daryl's trade vocabulary wins over SC's.** SC's catalog uses
  ALL-CAPS service-line labels; Daryl talks in plain English
  ("Plumber", "Sheet Rock Repair"). The dashboard should read in
  Daryl's voice, not SC's. Brenk-custom trades coexist with the SC
  catalog — if the picker gets noisy we can group/sort or add an
  archive flag later.
- **`service_area` is free text, not an enum.** Too varied (and too
  early) to enumerate. Most vendors land on "Austin & San Antonio";
  the outliers ("Anywhere", "Longview only") need exactly the
  granularity the operator wants to give them.
- **`localhost` is a trap in Node 22.** Always pin
  `NEXT_PUBLIC_API_URL` to `127.0.0.1` for local dev — the dual-stack
  fallback in undici will lose you 20 minutes the first time it bites.
- **One-off scripts in `backend/scripts/` are valuable artifacts.**
  Two new this session — `seed_daryl_vendor_contacts.py` and
  `export_vendors_for_cutover.py` — document operational decisions
  in executable form. They're committed to the repo on purpose.

### Up Next

1. **Dashboard pipeline funnel.** Replace the placeholder home page
   with the Tailwind UI cashflow-style stat layout: counts at each
   pipeline stage (pink / yellow / yellow+👤 / yellow+💬 / orange /
   green / green+💵 / invoiced) with avg-age callouts, plus a
   "Stuck right now" panel surfacing WOs sitting too long in any
   stage.
2. **Invoice queue.** Tabbed list ("Ready to mark up" / "Marked up,
   ready to send" / "Sent" / "Paid") + invoice detail layout (Tailwind
   UI invoice template). This is Sue's-clipboard replacement and
   directly addresses Daryl's biggest "WO got lost" failure mode.
3. **Markup helper.** Settings page captures Daryl's markup-board
   reference (per-trade defaults? Per-vendor defaults? Just notes?
   Open question for Daryl). Surfaces inline on the invoice-detail
   view.
4. **Junction table for multi-vendor assignment.** Today's model is
   a single `assigned_vendor_id` on the WO — fine for now, but Daryl
   sometimes splits one WO across two trades (locksmith + electrical,
   say). Schema migration to a `wo_vendor_assignments` join table
   when the funnel work surfaces the need.
5. **Production cutover.** Spin up the second free-tier Supabase
   project, run `alembic upgrade head`, run the worker once to seed
   `trades` and `vendors` from prod SC, then
   `python scripts/export_vendors_for_cutover.py | psql "$PROD..."`
   and click Sync. Targeting end of Phase 1.

### Open questions for the next session

- How does Daryl want to express his markup-board rules?
  Static reference card editable in Settings? Per-trade default %?
  Per-vendor default? Just notes he can refer to? — still open from
  prior sessions, becomes blocking when we start the invoice queue.
- Should the trades picker visually group Brenk-custom vs SC-catalog
  trades, or sort them together alphabetically? Worth a UX call once
  Daryl has actually used it.

---

## Session: May 18, 2026 — ~4.5 hours

First real day on the dashboard. By the end of the session a signed-in
user can see all 341 of Brenk's work orders, color-coded by status,
click into the full detail page (with notes timeline + workflow
pipeline view), and the SC deep-links land on the correct sandbox URL.

### Accomplishments

**Dashboard plan refinement (commit `8172098`):**
- Captured Daryl's full email-to-invoice workflow as the canonical
  reference: pink email request → yellow dispatch confirmed → Brenk
  texts sub-vendor → vendor on-site via CubeSmart app → orange
  complete → green store-confirmed → Sue's clipboard → Daryl markup →
  invoice in SC.
- Distilled the failure modes (vendor never actually texted, Sue's
  clipboard pile, Daryl forgets to invoice after paying vendor on his
  phone) into the lifecycle stages table in CLAUDE.md.
- Confirmed the Phase 1 read-from-SC / write-to-Brenk-only scope and
  added the Invoice Queue page to the build order.

**Next.js dashboard scaffold (commit `c99495a`):**
- Initialized `frontend/` with Next.js 16, React 19, Tailwind 4, App
  Router, Turbopack. Required upgrading Node 18 → 22 via nvm.
- Adapted the Tailwind UI "Dark sidebar with header" reference shell
  into `components/AppShell.tsx`. Real nav (Dashboard / Work Orders /
  Vendors / Reports / Settings), active-link highlighting via
  `usePathname()`, placeholder user menu, mobile drawer.
- Placeholder pages for each nav route.

**Supabase Auth on the frontend (commit `150ded0`):**
- `@supabase/ssr` cookie-aware factories for browser + server.
- `proxy.ts` (Next 16's rename of `middleware.ts`) refreshes sessions
  on every request and bounces unauthenticated traffic to /login,
  preserving the originally requested path in `?next=`.
- `/login` server-action sign-in form; `/auth/sign-out` route handler
  cleared via plain `<form method="POST">` from the user menu.
- Route group restructure: signed-in pages live under `(app)/` with
  their own layout that wraps everything in the shell with a
  server-fetched user. `/login` skips the shell.
- AppShell now shows the real signed-in user's email in the top bar.

**Backend JWT verification for ECC P-256 tokens (commit `8840a5f`):**
- Charles's Supabase project had migrated to ECC P-256 signing keys
  three days before this session, so every fresh access token from a
  sign-in would have been rejected by the existing HS256-only backend.
- Rewrote `app/core/auth.py` to dispatch on the token's `alg` header:
  HS256 still uses `SUPABASE_JWT_SECRET` (keeps existing tests
  working); ES256/RS256 verifies against the project's JWKS, fetched
  once and cached for an hour with one cache-bust retry on `kid` miss.
- `scripts/test_backend_auth.py` end-to-end check: signs in via
  Supabase Auth REST, takes the returned ES256 token, calls our
  backend. Verified locally: `status: 200, total: 327` against a
  fresh sign-in.

**Work Orders list (commit `816de9f`):**
- `lib/api/server.ts` typed `apiFetch` helper. Reads the Supabase
  access token from the cookie session, attaches `Authorization:
  Bearer`, surfaces typed `ApiError` on non-2xx, uses `cache: 'no-store'`
  so each render hits the API.
- `lib/api/types.ts` mirrors the backend Pydantic schemas; TODO to
  codegen from `/openapi.json` once the shapes settle.
- `lib/api/work-orders.ts` exposes `listWorkOrders`,
  `getWorkOrder`, `listWorkOrderNotes`.
- `StatusBadge` component pins a consistent color mapping per
  CLAUDE.md (yellow IN PROGRESS, green COMPLETED, pink OPEN/NEW,
  gray CANCELLED, red EXPIRED) — Daryl learns it once.
- `StatusFilter` (client component) updates `?status=` via
  `router.push()` and resets `?page=`.
- `Pagination` (server component) prev/next links built from current
  search params.
- The list page reads all of this together; renders an 8-column
  table with status badge, WO#, location, trade, priority, NTE,
  scheduled date, relative-time updated.

**Work Order detail + sort change (commit `d88069a`):**
- Backend list endpoint now orders by `sc_work_order_id DESC` —
  matches how SC's own UI shows WOs (newest at the top), which is
  what Daryl is already used to.
- New `/work-orders/[id]` dynamic route with two-column layout. Left
  column: details grid (trade, priority, dates, caller, etc.) +
  description + notes timeline. Right rail: workflow checklist + SC
  deep-link.
- `WorkflowChecklist` derives stage state from WO data + (future)
  Brenk-internal flags. SC-derived stages (Accepted, Dispatch
  confirmed, Work complete, Closed by store, Invoiced) show real
  status. Brenk-internal stages (Sub-vendor assigned, Vendor
  notified, Vendor on-site, Ready to invoice, Markup decided) show
  as "Not tracked yet" with notes pointing at when they ship.
- `NotesTimeline` renders the notes feed chat-thread style: avatar
  initials, author + company + relative time, "System" badge for
  SystemNote entries, HTML-stripped body for safety.
- 404 handling via Next's `notFound()` when the backend returns 404.
- `NEXT_PUBLIC_SC_WEB_URL` env var so the "Open in ServiceChannel"
  deep-link can be environment-aware. Sandbox default
  `https://sb2.servicechannel.com`; the URL pattern is
  `/sc/wo/Workorders/index?id=<sc_id>` (provided by Charles).

**Bonus: refreshed the sandbox data mid-session.** Charles flagged
that the dashboard was missing WOs from May 11+. Cause was the
Procrastinate worker wasn't running (the periodic sync needs a
worker process alive). Ran `scripts/test_sync.py` manually; pulled
in 6 new WOs (327 → 333 → 341 by end) and re-fetched ~2,000 notes
for WOs whose count had grown.

### Decisions & Observations

- **Use SC's color language directly** for status badges. Daryl's
  already fluent in pink/yellow/orange/green; teaching him a
  different palette would just be friction.
- **`@supabase/ssr` over deprecated `auth-helpers-nextjs`.** Cookie-
  based session handling is the modern Supabase pattern for SSR.
  Worth flagging if you read old tutorials — they'll point at the
  wrong package.
- **Next.js 16 renamed `middleware.ts` → `proxy.ts`.** Same shape,
  same runtime, new name. `AGENTS.md` (autogenerated by
  create-next-app) explicitly warns to heed Next 16 deprecation
  notices — that paid off here.
- **Next 16 made `params` and `searchParams` into Promises.** Every
  page that reads them needs `await`. Several training-data examples
  online still show them as plain objects.
- **Charles's Supabase project rotated JWT signing keys 3 days
  before we got to auth.** Caught at smoke-test time, not in code.
  Worth a note: if you ever add a new server that verifies Supabase
  tokens, default to JWKS-based verification, not the legacy HS256
  shared secret.
- **Server components can't have event handlers.** The status filter
  needed extracting to a Client Component to use the `onChange`
  pattern. Pages stay server, interactivity gets its own file.
- **Worker process must be running** for the every-5-min sync to
  actually run. Currently lives in a separate terminal locally;
  Fly.io's `fly.worker.toml` will keep it alive in production.
  Documented in the local-development runbook.
- **SC sandbox throttling is real and our retry path handles it.**
  Today's notes resync hit the 40 req/min cap several times; the
  `Retry-After` wait-and-retry path soaked the slowdowns cleanly,
  no errors.

### Up Next

1. **Vendors backend.** Schema migration to expand the existing
   `vendors` table with contact preferences, payment terms, mobile-
   app capability, etc. New CRUD endpoints
   `GET/POST/PATCH/DELETE /api/v1/vendors`.
2. **Vendors page.** List + per-vendor detail + add/edit modal +
   workload view + Tailwind UI calendar of scheduled WOs.
3. **Wire the Sub-vendor assigned stage into WO detail** once the
   Vendors API exists — moves the checklist from "Not tracked yet"
   to interactive.
4. **Dashboard pipeline funnel** (replace the placeholder home page).
5. **Invoice queue** (replaces Sue's clipboard).

### Open question carried into the next session

- Does Charles have an existing vendor list (spreadsheet, contacts)
  to import? Still open from previous sessions — would inform whether
  the Vendors page launches empty or pre-populated.

---

## Session: May 16, 2026 (evening) — ~2.5 hours

This session closed out the Phase 1 backend. With the work below committed,
every backend deliverable from the Phase 1 plan is functionally complete.
The remaining open item is the Next.js dashboard scaffold.

At the end of the session, Charles and Claude held a dashboard-planning
conversation (no code written) that settled scope, page set, and the
read-write split. Captured in the new **Dashboard Plan** section of
CLAUDE.md. Highlights:

- Tailwind UI "Dark sidebar with header" shell as the foundation
  (reference code stashed at `docs/design/dashboard-shell.tsx`)
- Five sidebar items: Dashboard, Work Orders, Vendors, Reports, Settings
- Pages to build in order: shell+login → WO list → WO detail → Vendors
  CRUD → kanban → "needs attention" home → per-vendor calendar
- Color-code statuses consistently across all views
- **Phase 1 writes go to Brenk-internal fields only.** SC write-through
  deferred to Phase 1.5 / early Phase 3 (needs an SC write-API
  exploration session first — those endpoints are unmapped)
- Open question for next session: does Charles have an existing vendor
  list (spreadsheet/contacts) to import, or start empty?

### Accomplishments

**Recency-filter revisit (commit `5b32d7e`):**
- Charles flagged the concern that the scheduled sync skipping all 327
  sandbox records (because the data is older than the 24-hour lookback)
  would silently drop long-lived in-progress WOs in production.
- Decided to **drop the filter entirely**, not redesign it. At Brenk's
  scale (~8 WOs/day, ~327 sandbox total), full pagination every 5
  minutes costs ~7 SC API requests per tick — trivially cheap. The
  upserter is already idempotent, so resyncing unchanged WOs is a
  no-op.
- Renamed `sync_recent_work_orders(lookback_hours)` →
  `sync_all_work_orders()`. Dropped the cutoff/skipped logic and the
  `lookback_hours` parameter from both worker tasks.
- Removed dead config: `SC_SYNC_INTERVAL_SECONDS` (cron is hardcoded in
  the `@periodic` decorator) and `SC_SYNC_LOOKBACK_HOURS` (filter is
  gone).
- End-to-end verified: the full sweep imported the 160 previously-skipped
  records, taking the DB from 167 → 327 WOs, 46 → 54 locations,
  21 → 27 trades. `wo_status_history` stayed at 0 — confirms the
  upserter correctly no-op'd the 167 already-synced records.

**Work-order notes sync (commit `73ec534`):**
- New `app/services/sync/notes.py` with three building blocks:
  `upsert_note` (keyed on `sc_note_id`), `sync_notes_for_work_order`
  (fetches + upserts the full notes thread), and
  `sync_notes_for_sc_work_order_id` (looks up the WO by its SC id then
  delegates).
- Smart trigger logic in the orchestrator: only fetch notes for a WO
  when the incoming `notes_count` from the list payload exceeds the
  actual count of `wo_notes` rows we have stored. **Critical bug caught
  mid-implementation** — initially compared against the WO's
  denormalized `notes_count` column, which would have always matched and
  never triggered backfill. Comparing against actual stored row count
  is the correct semantic.
- `sync_work_order_detail` Procrastinate task is no longer a stub — it's
  a thin wrapper around `sync_notes_for_sc_work_order_id`, suitable for
  ad-hoc "refresh notes for this WO" triggers later from the UI.
- New `WorkOrderNoteRef` schema + `GET /api/v1/work-orders/{id}/notes`
  endpoint, ordered by note number with deterministic fallback.
- End-to-end verified: **2,930 notes backfilled** across all 327 WOs in
  one ~16-minute run. Sustained 4 SC throttle events (40 req/min sandbox
  cap), all handled cleanly via the existing `Retry-After`
  wait-and-retry path. First real-world exercise of that code path.

**Supabase JWT auth on the API (commit `6e5dc4b`):**
- New `app/core/auth.py`: `CurrentUser` model + `get_current_user`
  FastAPI dependency. Validates HS256-signed Supabase JWTs using
  `SUPABASE_JWT_SECRET`, checks `aud="authenticated"` and `exp`,
  surfaces `sub`/`email`/`role` from the claims.
- Uses FastAPI's `HTTPBearer` security scheme — Swagger UI at `/docs`
  now has an "Authorize" button for interactive testing.
- Applied at the v1 router level via
  `APIRouter(dependencies=[Depends(get_current_user)])` so every
  current and future v1 endpoint is protected in one place.
  Top-level `/health` stays open for Fly.io probes.
- New `tests/integration/conftest.py` with a `mint_jwt()` helper that
  forges Supabase-shaped JWTs signed with the same secret the backend
  verifies against. Tests run end-to-end without a real Supabase Auth
  round-trip.
- 6 new auth tests covering: missing header, malformed bearer, expired
  token, wrong audience, wrong signature, `/health`-stays-open.
- Updated existing endpoint tests to authenticate (otherwise they'd
  all 401 after this change).

### Decisions & Observations

- **Drop, don't refactor.** The recency filter felt like clever
  optimization but at our scale it was solving a non-problem. Removing
  it was a net-negative-LoC win.
- **Compare against actual DB state, not denormalized counts.** When
  computing whether to re-fetch notes, what matters is what we actually
  have stored, not what we thought we had. The `WorkOrder.notes_count`
  column is a denormalized SC-reported value, useful for the API
  response but not for "do we need to fetch more notes?" decisions.
- **SC sandbox throttling kicked in for the first time.** 4 throttle
  events during the notes backfill. Our client's `Retry-After`
  wait-and-retry path (added back in Phase 1 scaffolding, never
  previously exercised under load) worked flawlessly — every throttled
  request retried after the prescribed wait and succeeded. Good to
  know that path is solid before production volume.
- **Router-level auth dependency is the right idiom.** Decorating each
  endpoint with `Depends(get_current_user)` would be redundant boilerplate
  that's easy to forget on a new endpoint. Setting it on the
  `APIRouter` itself means new endpoints inherit auth by default and
  exempting one (like `/health`) is the explicit, conspicuous action.
- **`HTTPBearer` Swagger integration is a nice touch.** Free
  developer-ergonomics win — you click "Authorize" in the docs UI,
  paste a JWT, and every subsequent "Try it out" includes it. Useful
  for ad-hoc exploration without writing a script.

### Up Next

1. **Next.js dashboard scaffold** — the last open Phase 1 deliverable.
   Multi-session piece of work. First commit: initialize the Next.js
   project, set up Tailwind, get a "Hello world" page rendering, wire
   up the Supabase JS client for auth.
2. **Pre-existing ruff errors** (~10 across `config.py`,
   `migrations/env.py`, and the autogenerated initial migration). Small
   focused cleanup pass.
3. **Push to origin** — branch is now 8 commits ahead. We've been
   building offline; before the next session it's worth pushing so
   GitHub has the work.
4. **`LICENSE` leftover merge-conflict markers** — still uncommitted in
   the working tree. Tiny separate fix when convenient.

---

## Session: May 16, 2026 (afternoon, continued) — ~2.5 hours

### Accomplishments

**Pagination + filter-semantics fix in the SC client (commit `b457509`):**
- Investigated SC's `/v3/workorders` Swagger and confirmed two things:
  the endpoint paginates via `page`/`pageSize` (max 50, default 50), and
  **there is no `updatedSince`/`updatedFrom` parameter**. Our previous
  client was passing `updatedFrom=<timestamp>` which SC silently ignored
  — so `sync_recent_work_orders(lookback_hours=N)` was effectively just
  fetching the first 50 records regardless of `N`.
- Replaced `list_work_orders(limit, offset, updated_since)` with
  `list_work_orders_page(page, page_size, sort)` and an async iterator
  `iter_work_orders()` that paginates until a partial/empty page,
  capped at 200 pages (10K records) for safety.
- `sync_recent_work_orders` now iterates all pages and filters
  client-side by `UpdatedDate >= cutoff`. Summary gained a `skipped`
  counter.
- 4 respx-based unit tests for pagination, empty pages, the max-pages
  safety cap, and pageSize clamping.
- Updated `docs/architecture/servicechannel-api.md` with the corrected
  pagination scheme + the lack of an `updatedSince` filter.
- End-to-end verified: sandbox has **327 WOs**, not 50 — we'd been
  silently truncating data. With the new pagination, the smoke test
  fetched 327, skipped 160 (older than 30 days), upserted 167.
  Idempotent on rerun.

**Recurring schedule via Procrastinate periodic (commit `bec631e`):**
- Applied Procrastinate's job-queue schema to Supabase (one-time setup).
- Added `scheduled_sync_work_orders(timestamp)` decorated with
  `@procrastinate_app.periodic(cron="*/5 * * * *")` — runs every 5
  minutes, delegates to `sync_recent_work_orders` with the lookback
  from settings. Kept the existing `sync_work_orders(lookback_hours)`
  task for ad-hoc/manual invocations.
- Discovered the Procrastinate CLI requires the **full dotted path to
  the App variable** (`app.workers.app.procrastinate_app`), not just
  the module path. Updated `docs/runbooks/local-development.md` with
  the corrected invocation, a note about periodic schedule discovery,
  and how to defer tasks ad-hoc.
- Verified end-to-end: worker boots, registers the cron, fires the
  first tick immediately (Procrastinate fires missed periodic ticks on
  startup), paginates all 7 pages, returns a clean success result.

**Note on the recency filter:** during the scheduled-sync verification,
the very first run skipped all 327 records because the 24-hour default
lookback excluded everything in the sandbox. Charles flagged the
concern that in production, long-lived in-progress WOs might be
filtered out if they haven't been touched recently. Added a TODO in
`work_orders.py` to revisit before production — likely either a
separate full-sync mode or dropping the filter entirely and relying on
upsert idempotency.

**REST endpoints for work orders (commit `d374dfb`):**
- Added Pydantic response schemas in `app/schemas/work_order.py`:
  `WorkOrderSummary` (list view), `WorkOrderDetail` (single view),
  nested `ClientRef`/`LocationRef`/`TradeRef`/`VendorRef`, and a
  paginated envelope.
- Implemented `GET /api/v1/work-orders/` with filters (status,
  client_id, trade_id, updated_since) and pagination (page, page_size
  up to 200). Orders by `sc_updated_date desc` with deterministic
  fallback on `id desc`. Eager-loads `client`/`location`/`trade`.
- Implemented `GET /api/v1/work-orders/{id}` returning full detail
  with all related refs eager-loaded. 404 on unknown id.
- 7 integration tests using `httpx.AsyncClient` + `ASGITransport`
  against the real dev DB. Total test count is now **26 passing**.
- Manually smoke-tested with curl: list returns 167 WOs with embedded
  refs, `status=COMPLETED` filter narrows to 54, detail returns full
  payload, unknown id returns 404.

### Decisions & Observations

- **Test infrastructure: FastAPI's sync `TestClient` doesn't play well
  with SQLAlchemy's async engine** — it spins up a new event loop per
  request, but the async connection pool caches connections tied to
  the first loop, so subsequent tests fail with "Event loop is closed."
  The fix: use `httpx.AsyncClient` + `ASGITransport` and override
  `get_async_db` with a `NullPool`-backed engine for tests. Documented
  in the integration test module's docstring for future reference.
- **No `updatedSince` on `/v3/workorders`.** Confirmed via Swagger.
  All recency filtering happens client-side after pagination.
- **Procrastinate fires missed periodic ticks on startup.** So
  restarting the worker doesn't lose a tick. Convenient.
- **API filters use internal database ids, not SC ids.** A consumer
  filtering by `client_id=1` means "our internal Client.id = 1" not
  "sc_subscriber_id". The Swagger docs make this clear via the
  parameter descriptions.

### Up Next

1. **Reconsider the recency filter** before doing anything else
   production-bound — Charles's concern is valid and the scheduled run
   skipping all 327 sandbox records is direct evidence.
2. Implement `sync_work_order_detail` for notes: call
   `/v3/workorders/{id}/notes`, transform, upsert into `wo_notes`.
   Decide trigger (every WO sync vs. only when notes_count changes).
3. Wire up Supabase Auth + JWT verification on the FastAPI endpoints.
4. Address the 10 pre-existing ruff errors (`config.py` uppercase
   property names, `migrations/env.py` unused noqa, autogenerated
   migration's old `typing.Sequence` import).
5. Begin the Next.js dashboard scaffold (Week 4).

---

## Session: May 16, 2026 (afternoon) — ~1.5 hours

### Accomplishments

- Built the work-order sync service in three layers (`app/services/sync/`):
  - `transformers.py` — pure functions translating SC payloads to ORM
    column dicts. Handles UTC timestamp parsing, the nested-`Location.Id`
    quirk, and missing-field defaults.
  - `upserter.py` — async get-or-create helpers keyed on SC natural keys
    (`sc_subscriber_id`, `sc_location_id`, `sc_trade_id`,
    `sc_work_order_id`). Includes automatic `WorkOrderStatusHistory`
    emission when a WO's primary/extended status changes between syncs.
  - `work_orders.py` — orchestrator. One commit per WO so a bad payload
    can't poison the batch. Returns `{fetched, upserted, errors}`.
- Replaced the stub bodies in `app/workers/tasks.py` — `sync_work_orders`
  is now a thin delegation to `sync_recent_work_orders`.
- Added scrubbed fixture `tests/fixtures/workorder_list.json` (safe to
  commit — no real client names) and 11 unit tests covering every
  transformer path. Full suite: 15/15 passing.
- Wrote `scripts/test_sync.py` end-to-end smoke test and ran it twice
  against SC Sandbox2 + Supabase:
  - **Run 1:** fetched 50 / upserted 50 / 0 errors. Populated 1 client,
    24 locations, 10 trades, 50 work orders, 0 status history (correct).
  - **Run 2 (idempotency check):** identical row counts, 0 errors,
    0 spurious status history entries — confirms the upsert logic
    correctly no-ops when nothing changed.
- Fixed two latent dependency gaps that would have crashed first run:
  - Added `psycopg[binary]` — Procrastinate uses `psycopg` v3 which only
    ships the wrapper without a backend by default
  - Switched `sqlalchemy` → `sqlalchemy[asyncio]` to pull in `greenlet`,
    required by SQLAlchemy's async engine

### Decisions & Observations

- **One commit per WO during sync, not one batch transaction.** A single
  malformed payload can't take down a full sync run. At ~8 WOs/day the
  per-row commit overhead is irrelevant.
- **Status-change detection happens in the upserter, not the orchestrator.**
  Keeps the orchestrator pure-orchestration and means any future caller
  (e.g., a webhook handler) automatically gets the same history behavior.
- **SC `limit` quirk re-confirmed.** Client requested `limit=100` and got
  back exactly 50 records. Sandbox appears to cap responses at 50
  regardless of the requested limit. **The client does not yet paginate.**
  For ~8 WOs/day with `lookback_hours=1`, this is fine; backfill scenarios
  will need a pagination loop.
- **Verbose SQLAlchemy echo logging is on whenever `DEBUG=true` in `.env`.**
  Wired up in `db/session.py`. Useful during development; toggle off for
  production.
- All raw SC payloads are persisted in `raw_data` JSONB columns as designed.
  Confirmed during smoke test — JSONB columns contain the full
  unmodified payload, ready for forward-compatible schema changes.

### Up Next

1. Implement pagination in the SC client's `list_work_orders` (loop
   `offset` until fewer than `limit` records returned)
2. Schedule `sync_work_orders` as a recurring Procrastinate task (every 5
   minutes? — see `SC_SYNC_INTERVAL_SECONDS` in config)
3. Build the FastAPI REST endpoints in
   `app/api/v1/endpoints/work_orders.py` to expose the synced data
4. Implement `sync_work_order_detail` for notes (call
   `/v3/workorders/{id}/notes` and upsert into `wo_notes`)
5. Tackle Phase 1 cleanup: 10 pre-existing ruff errors in `config.py`,
   `migrations/env.py`, and the autogenerated initial migration

---

## Session: May 16, 2026 (late morning) — ~30 min

### Accomplishments

- Configured Supabase database connection in `backend/.env`:
  - Reset database password to alphanumeric (avoids URL-encoding for `#`)
  - Added correct driver prefixes (`postgresql+psycopg2://` for sync,
    `postgresql+asyncpg://` for async)
  - Both URLs point at the session pooler (port 5432) — see decision below
- Generated initial Alembic migration `9a84643a059f` via `--autogenerate`
  from existing SQLAlchemy models
- Applied migration to Supabase — 7 tables created (`clients`, `trades`,
  `vendors`, `locations`, `work_orders`, `wo_notes`, `wo_status_history`)
  plus 15 indexes, FK constraints, and JSONB `raw_data` columns
- Fixed broken `ruff` post-write hook in `alembic.ini` (was using
  `console_scripts` entrypoint; switched to `exec` type)
- Formatted the migration file that was generated before the hook fix

### Decisions & Observations

- **Both `DATABASE_URL` and `DATABASE_URL_ASYNC` point at the session pooler
  (5432) for now**, not the transaction pooler (6543). At ~8 WOs/day the
  transaction pooler buys us nothing and would require special handling for
  asyncpg's prepared statement cache. We can flip the async URL to 6543 if
  we ever hit pooling pressure (we won't, at this volume).
- **Single Supabase project for now (no dev/prod split).** The "PRODUCTION"
  label in the dashboard is just metadata; Supabase branching requires Pro.
  Free tier permits 2 projects, so we'll spin up a separate prod project at
  end of Phase 1 right before Daryl starts using the dashboard. Until then,
  this single project is treated as dev — schema iteration is expected.
- Confirmed `DATABASE_URL_ASYNC` was identical to the sync URL prior to this
  session — a latent bug that would have crashed FastAPI at first runtime.
  Now fixed.

### Up Next

1. Implement real bodies of `app/workers/tasks.py` for `sync_work_orders`
   and `sync_work_order_detail`
2. Build the sync service in `app/services/sync/` that translates SC
   responses into ORM records
3. Implement REST endpoints in `app/api/v1/endpoints/work_orders.py`
   (currently returning 501)
4. Wire up Supabase Auth + JWT verification

---

## Session: May 16, 2026 (early morning) — ~1 hour

### Accomplishments

- Resolved Python environment configuration issues (Python 3.10 → 3.13 migration)
- Cleaned up `pyproject.toml` by removing tight version pins that were causing
  pip resolver to thrash
- Successfully installed all backend dependencies on Python 3.13
- **Verified end-to-end ServiceChannel authentication** via
  `scripts/test_sc_auth.py`:
  - OAuth password grant flow working
  - Access token obtained, stored, and refreshable
  - Successfully fetched live work orders from Sandbox2
  - Sample data captured to `docs/api-samples/`

### Decisions & Observations

- Pinned Python target to 3.13 in both `pyproject.toml` and `pyrightconfig`-
  adjacent settings (ruff, mypy). Reason: 3.10 caused dependency resolution
  failures due to our use of newer pydantic-settings versions.
- Removed tight version pins from `pyproject.toml`. Will re-pin only when we
  hit a real compatibility issue. Loose pins keep pip resolution fast and
  predictable for a project with so few moving parts.
- Discovered the `/v3/workorders` endpoint returns 50 records even when
  `limit=5` is requested. Real pagination parameter name unknown — to be
  investigated when building the sync worker.

### Up Next

1. Configure Supabase database URLs in `.env`
2. Generate initial Alembic migration from SQLAlchemy models
3. Apply migration to Supabase, verify tables in the dashboard
4. Begin implementing real sync worker bodies

---

## Session: May 15, 2026 — ~3.5 hours

### Accomplishments

- Registered application with ServiceChannel in the Sandbox2 environment;
  obtained client ID and secret
- Explored ServiceChannel v3 REST API surface:
  - Work order list endpoint: `GET /v3/workorders`
  - Work order detail endpoint: `GET /v3/workorders/{id}`
  - Notes endpoint: `GET /v3/workorders/{id}/notes`
- Confirmed sandbox contains real-shaped data (real client and location names)
  — flagged as a confidentiality concern
- **Documented attachment endpoint as not currently accessible.** Tried `v1`,
  `v2`, `v3`, and unversioned paths — none work. Attachment metadata is
  reachable via the notes endpoint as a fallback.
- Designed the initial database schema from real ServiceChannel response data:
  `work_orders`, `clients`, `locations`, `vendors`, `trades`, `wo_notes`,
  `wo_status_history`
- Built out complete backend project structure:
  - FastAPI app with health check, CORS, Sentry integration
  - Core utilities: config (pydantic-settings), structured logging, exceptions
  - Database layer: SQLAlchemy Base, sync + async sessions, Alembic setup
  - SQLAlchemy ORM models matching the designed schema
  - ServiceChannel OAuth client with token caching, refresh, retry, and
    `Retry-After` handling
  - ServiceChannel API client wrapping work orders, detail, and notes endpoints
  - Procrastinate worker setup with task stubs
  - Standalone `test_sc_auth.py` script for end-to-end auth verification
  - Smoke tests for the auth module using respx mocks
- Created infrastructure config:
  - Dockerfile for the backend
  - Two Fly.io configs (web + worker)
  - `.dockerignore` and `.gitignore` at appropriate levels
- Wrote project documentation:
  - Top-level README
  - `docs/architecture/overview.md` — system design with diagram
  - `docs/architecture/servicechannel-api.md` — quirks, gotchas, open questions
  - `docs/architecture/database-schema.md` — design rationale
  - `docs/runbooks/local-development.md` — clone-to-running setup guide
- Initialized GitHub repository and pushed initial codebase

### Decisions & Observations

- **Postgres-as-queue (Procrastinate) over Redis.** Eliminates one managed
  service and gives us transactional consistency between business data and
  job state. Adequate for our volume (~8 WOs/day).
- **`raw_data` JSONB column on every SC-sourced table.** Cheap insurance
  against missing or mismodeled fields; allows backfilling without re-fetching.
- **Vendor model decoupled from ServiceChannel Providers.** Brenk maintains
  sub-vendors that may not exist in SC as Providers.
- **Status stored denormalized on `work_orders`** (`primary_status` +
  `extended_status` as columns, not a separate `statuses` reference table).
  Reference table can be added later if we need per-status metadata.
- **All timestamps stored as UTC.** SC provides both UTC and DTO variants;
  we keep UTC and convert at display time.
- **HTTPS to GitHub instead of SSH.** SSH key setup deferred — not worth the
  delay right now.
- Sandbox2 confidentiality: real entity names appear in test data, so sandbox
  responses are treated with production-level care. Sample files saved to
  `docs/api-samples/` should be scrubbed or gitignored.

### Up Next

1. Set up local Python environment, install dependencies, verify SC auth works
   end-to-end on the machine
2. Configure Supabase and apply initial migration
3. Implement real sync worker bodies

---

## Pre-development Planning Sessions (prior to May 15)

### Discovery & Proposal Phase

Captured across multiple prior conversations with Claude. Highlights:

- Evaluated the family business's pain points: manual juggling of
  ServiceChannel work orders, sub-vendor coordination via email/phone,
  QuickBooks entry, and customer invoicing
- Mapped out a five-phase platform proposal:
  1. Foundation & ServiceChannel integration
  2. QuickBooks integration & invoice automation
  3. Vendor communication automation
  4. Intelligence & analytics
  5. Public-facing business website
- Compared technology choices:
  - Backend language: settled on Python (FastAPI) for ecosystem and AI tooling
  - Job queue: Redis+Celery vs. RabbitMQ vs. Procrastinate — picked
    Procrastinate (Postgres-backed) for simplicity at our scale
  - Frontend: Next.js vs. HTMX vs. Retool — picked Next.js for polished UX
  - Hosting: Railway vs. Fly.io — picked Fly.io (cleaner fit with separate
    Supabase Postgres, slightly cheaper at our scale)
  - Database/auth: Supabase consolidates Postgres + Auth + storage
- Estimated monthly operating costs: $60-$180/month all-in once Phase 4 is
  live (mostly Anthropic Claude API + email/SMS)
- Settled on pricing: **$50/hour during active development** (infrastructure
  costs absorbed), transitioning to a **$300/month retainer** post-launch
  covering ongoing infrastructure, maintenance, and minor improvements
- Considered the sellability angle: this platform demonstrably reduces
  owner-dependency, externalizes vendor and pricing knowledge, and produces
  clean financial data — all of which materially improve the business's
  eventual sale multiple
- Proposal accepted, work began

---

## How to Use This File

- Add a new entry at the **top** at the end of each work session
- Keep entries brief but specific — what was actually accomplished, decisions
  made, and what's queued next
- "Decisions & Observations" is the most valuable section long-term — it
  captures the *why* behind choices so future Charles (or future Claude)
  doesn't have to reconstruct reasoning
- Reference this file when generating invoice descriptions