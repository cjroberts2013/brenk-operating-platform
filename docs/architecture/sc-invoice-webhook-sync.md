# ServiceChannel Invoice Webhook Sync — Implementation Spec

**Status:** Build-ready (2026-06-10). External-model draft, evaluated and
adapted to the Brenk stack by Claude. This is the canonical spec to
implement against.

**Why this exists:** `GET /v3/odata/invoices` (the read that would let us
poll invoice state) is still permission-blocked (401 / code 504, retested
2026-06-10). Webhooks are a separate permission path and push the full
invoice lifecycle (Open → Approved → Paid → Void / Rejected) to us in
real time. This is exactly the read-back half of Phase 1.5, achieved
without the blocked endpoint.

**Supersedes** the research notes in `servicechannel-api.md`
("Auto-sync architecture — webhook-driven", "Webhooks — full spec",
"Status → tab mapping"). Those remain as background; this doc is what we
build.

---

## 0. Evaluation of the plan (what we kept, what we changed)

The plan is sound on every hard correctness point. **Keep as-is:**

- **Ack fast, process later.** Verify signature → store raw row → return
  200 in the request path; all business logic in the worker. SC requires
  a 2xx within 5 s or it retries 3× at 5-min spacing and then drops the
  event permanently. Receiver uptime is the data-loss budget.
- **Raw payload is sacred.** We cannot re-fetch (read is blocked), so the
  webhook body is the only copy. Persist exact request bytes before any
  parse.
- **Idempotent via `sha256(raw_body)` dedupe key** + insert-or-ignore.
  Retries are byte-identical, so redelivery is a clean no-op.
- **Circuit-breaker protection.** 1,000 consecutive failures disables the
  webhook (12 h, then permanent). So the receiver returns 200 even for
  events it cannot process; failures are dead-lettered internally, never
  surfaced as a non-2xx.
- **Out-of-order safety** (skip stale scalar updates by `UpdatedDateDTO`,
  still append history), **empty `Labors`/`Materials` must not wipe line
  items**, and **EventType is authoritative** for terminal states
  (`InvoiceVoided` sample can still read `Status: OPEN`). All correct.
- **Backfill merge rules** (webhook wins; backfill only fills NULLs;
  idempotent re-runs). Correct.

**Adapted to our stack (the deltas that matter):**

1. **Use Procrastinate, not a hand-rolled poll loop.** We already run a
   Postgres-backed queue (`brenk-platform-worker`). The receiver defers a
   Procrastinate job per stored event; a periodic sweep is the safety net
   (see §5.2). No `FOR UPDATE SKIP LOCKED` loop to build.
2. **Schema as SQLAlchemy models + an Alembic migration**, not raw DDL.
   Postgres specifics below. The composite key with `COALESCE(...)` cannot
   be a literal PK in our ORM, so use a surrogate `id` PK + an expression
   unique index (see §4).
3. **Deploy on the existing Fly apps.** Receiver = a route on
   `brenk-platform-web` (already public HTTPS). Worker = the existing
   `brenk-platform-worker`. No new infra; the plan's "small VPS/PaaS" is
   already satisfied.
4. **Auth-exempt endpoint.** The route carries no Supabase-JWT
   dependency; the HMAC verifies authenticity. Precedent: the public
   `POST /api/v1/storefront/quote` endpoint already runs un-authed.
5. **Env var name `SC_WEBHOOK_SIGNING_KEY`** (matches the name already in
   our docs), one per environment, via `fly secrets`. Never commit, never
   log.
6. **One endpoint, routes by `EventType`:**
   `POST /api/v1/webhooks/servicechannel`. A webhook posts all its
   subscriptions (Invoice, and optionally WorkOrder) to one URL, so a
   single receiver that switches on `EventType` is correct.

**The value-add we add (the real payoff):** the plan builds a standalone
invoice store. For Brenk the win is **closing the pipeline loop** — link
each invoice to our `work_orders` row and let `InvoiceApproved` /
`InvoicePaid` drive the `/invoices` queue tabs and auto-derive paid
state, retiring the manual "Mark paid" button. That is precisely what the
blocked OData read would have given us. See §7.

**Scale note:** Brenk runs ~8 WOs/day. Do not over-engineer throughput.
Procrastinate handles this trivially; batch sizes / poll tuning are moot.
The correctness machinery (5-s ack, idempotency, out-of-order) still
matters; the high-volume machinery does not.

---

## 1. Architecture (our stack)

```
ServiceChannel ──POST──▶  POST /api/v1/webhooks/servicechannel      (brenk-platform-web, FastAPI)
                              │  verify HMAC over raw bytes
                              │  INSERT webhook_events (raw, pending)   [ON CONFLICT dedupe_key DO NOTHING]
                              │  defer Procrastinate job(event_id)
                              ▼  return 200  (<50 ms target, 5 s hard ceiling)
                     Procrastinate worker (brenk-platform-worker)
                              │  process_webhook_event(event_id)  +  periodic sweep of stale pending
                              ▼  idempotent upsert
        invoices · invoice_labors · invoice_materials · invoice_status_history
                              │  link wo_tracking_number → work_orders.sc_work_order_id
                              ▼
                     work_orders (sc_invoice_*, auto paid)  →  /invoices queue tabs
                              ▲
                              │  one-time import, source='backfill'
                  UI-exported Excel/CSV  ──▶  backend/scripts/backfill_invoices.py
```

---

## 2. [HUMAN] ServiceChannel webhook setup (CJ, in the SC UI)

Done **twice**: Sandbox2 and Production are separate systems with
separate logins, signing keys, and webhook configs. Required access:
**Provider Automation Admin** (the WebHooks tab is visible).

| | Sandbox2 | Production |
|---|---|---|
| Receiver URL | `https://<tunnel-or-staging>/api/v1/webhooks/servicechannel` | `https://brenk-platform-web.fly.dev/api/v1/webhooks/servicechannel` (or the API domain) |
| API base (ref) | `https://sb2api.servicechannel.com` | `https://api.servicechannel.com` |
| Caveat | **Sandbox2 wipes every weekend** — expect silence until you create new test invoices | Real invoices, fires once Active |

Steps (identical in each environment):

1. Provider Automation → **Integration → WebHooks**.
2. **Copy the Signing Key** (Show → Copy). Store as `SC_WEBHOOK_SIGNING_KEY`
   in that environment's secret store (`fly secrets set` for prod; `.env`
   for the dev/sandbox receiver). **Do not Regenerate** — it invalidates
   the key everywhere it is deployed (treat Regenerate as a coordinated
   secret rotation).
3. **+ Add Webhook** → Name `invoice-sync` (sandbox: `invoice-sync-sandbox`)
   → Status **Inactive** → URL = the receiver above (HTTPS, public).
4. **Ping URL** (receiver must be deployed/tunneled first). Fix
   connectivity before continuing.
5. **Add Subscription:** Object Type `Invoice`, Name `all-invoice-events`,
   leave Trades/Categories/Statuses filters **empty** (we want the full
   lifecycle incl. Paid/Voided/Rejected). Confirm.
6. *(Optional v1+)* second subscription, Object Type `WorkOrder`, name
   `all-wo-events` — the receiver routes by `EventType` already, and WO
   context (completion/status) enriches invoice records. Skip to keep v1
   tight.
7. **Save Webhook.** Flip to **Active** only after the receiver passes the
   smoke test (§9).

Limits (plenty of headroom): 20 webhooks/provider, 20 subscriptions/webhook.

---

## 3. Configuration (per environment)

| Var | Notes |
|---|---|
| `SC_WEBHOOK_SIGNING_KEY` | from the WebHooks page of that environment. Secret. Never commit/log. |
| `SC_ENV` | `sandbox` \| `production` — tags every stored row (we already have `SC_ENVIRONMENT`; reuse it). |

Dev (sandbox) runs against the `Brenk Dev` Supabase + local/tunneled
receiver; prod runs on `brenk-platform-web` against `Brenk Production`.
The two are already separate deployments with separate secrets, so the
"never share one signing key across both" rule is satisfied by our
existing dev/prod split.

---

## 4. Database schema (SQLAlchemy models + Alembic)

Five new tables. Build as SQLAlchemy 2.0 models, then
`alembic revision --autogenerate`. Postgres notes:

- `raw_body` → `LargeBinary` (BYTEA). Store exact request bytes.
- All timestamps `TIMESTAMPTZ`, UTC (our convention).
- Keep `sc_env` on every table (cheap provenance; harmless even though
  dev/prod are separate DBs).
- **`invoices` key:** the plan's `PRIMARY KEY (sc_env, invoice_number,
  COALESCE(wo_tracking_number,-1))` is not expressible as a literal PK in
  our ORM. Use a surrogate `id BIGINT PK` plus:
  - `UNIQUE INDEX ON invoices (sc_env, sc_invoice_id) WHERE sc_invoice_id IS NOT NULL`
  - `UNIQUE INDEX ON invoices (sc_env, invoice_number, COALESCE(wo_tracking_number, -1))`
    (expression index via `Index(..., text("coalesce(wo_tracking_number,-1)"), unique=True)`).
- **RLS:** our security posture enables RLS on every public table (backend
  is `postgres`/`bypassrls`, Data API disabled). The migration must
  `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` on all five new tables, same
  as the `faf100f05a60` migration did.

Tables (columns from the plan, kept verbatim except the key change):

- **`webhook_events`** (append-only raw log; the source of truth):
  `id` PK, `sc_env`, `received_at`, `raw_body` BYTEA, `sign_data`,
  `signature_valid` bool, `event_type`, `object_id`,
  `dedupe_key` UNIQUE, `status` (`pending|processed|skipped_duplicate|dead_letter|invalid_signature`),
  `error`, `processed_at`. Partial index on `(status) WHERE status='pending'`.
- **`invoices`** (materialized state): surrogate `id`, `sc_invoice_id`,
  `sc_env`, `invoice_number`, `wo_tracking_number`, `subscriber_id`,
  `provider_id`, `location_id`, `status`, `trade`, `category`,
  `description`, `currency`, `subtotal`, `invoice_tax`, `invoice_total`,
  `approval_code`, `batch_number`, `comments`, `invoice_date`,
  `posted_date`, `approved_date`, `paid_date`, `last_action_date`,
  `sc_updated_date`, `source` (`webhook|backfill`), `created_at`,
  `updated_at`. Plus the two unique indexes above.
- **`invoice_labors`** / **`invoice_materials`** (delete-and-replace per
  event that carries non-empty arrays): keyed by `sc_invoice_id`, fields
  per the SC line-item schema (`skill_level/labor_type/num_of_tech/hourly_rate/hours/amount`
  and `description/part_num/unit_type/unit_price/quantity/amount`).
- **`invoice_status_history`** (audit trail): `sc_invoice_id`,
  `event_type`, `status`, `changed_by`, `event_time`, `webhook_event_id`
  FK → `webhook_events.id`.

---

## 5. Receiver + worker (our stack)

### 5.1 Receiver — `POST /api/v1/webhooks/servicechannel` (FastAPI)

- Take a raw `Request`, read **`await request.body()`** for the exact
  bytes. Do **not** bind a Pydantic model on the body — re-serialized
  JSON breaks the HMAC.
- Verify: `expected = base64(hmac_sha256(key=SC_WEBHOOK_SIGNING_KEY.encode(), msg=raw))`,
  compare to the `Sign-Data` header with **`hmac.compare_digest`** (never `==`).
- Logic (target <50 ms):
  1. `valid = verify(raw, headers["Sign-Data"])`.
  2. Best-effort parse JSON → `event_type = body.get("EventType")`,
     `object_id = body.get("Object", {}).get("Id")`.
  3. Empty body (the UI **Ping**) → return **200**, store nothing.
  4. Non-empty body + invalid signature → insert row `status='invalid_signature'`,
     return **401**.
  5. Valid → `dedupe_key = sha256(raw).hexdigest()`; `INSERT ... ON
     CONFLICT (dedupe_key) DO NOTHING`; `defer` `process_webhook_event(id)`;
     return **200 `{"received": true}`**.
  6. Always 200 once stored, even for unknown `EventType` (worker decides).
- No auth dependency on this route. Also handle `GET`/`HEAD` on the path
  → 200 (some reachability pings use GET); `/health` already exists.

### 5.2 Worker — `process_webhook_event(event_id)` (Procrastinate task)

- Registered on `brenk-platform-worker`. Deferred per-receipt for low
  latency. **Safety net:** a `@periodic` task (every ~1 min) sweeps
  `webhook_events WHERE status='pending'` older than ~30 s and processes
  them — covers any defer gap and gives us at-least-once without a custom
  poll loop. (At 8 WOs/day, even periodic-only would be fine.)
- Because we already returned 200 to SC at receipt, Procrastinate
  retries/failures here are fully decoupled from SC's circuit breaker.
- Per event, in one DB transaction:
  1. Parse JSON; route on `EventType`:
     - Invoice events (`InvoiceCreated`, `InvoiceOpen`, `InvoiceApproved`,
       `InvoiceOnHold`, `InvoiceReviewed`, `InvoiceRejected`,
       `InvoiceApprovalCodeChanged`, `InvoiceVoided`, `InvoicePaid`,
       `InvoiceDisputed`, `InvoiceStarAdded`, `InvoiceStarRemoved`) →
       invoice upsert.
     - `WorkOrder*` / others → mark `processed` (no-op) for v1; extension
       point.
     - Unknown → `dead_letter` with a note; still counts as handled.
  2. **Invoice upsert (out-of-order safe):**
     - Match by `(sc_env, sc_invoice_id)`; else by
       `(sc_env, invoice_number, wo_tracking_number)` (how backfill rows
       get adopted and gain their `sc_invoice_id`).
     - `evTime = Object.UpdatedDateDTO ?? Object.LastActionDateDTO`. If the
       existing row's `sc_updated_date > evTime`, **skip scalar updates**
       (stale late delivery) but still append history.
     - Else upsert scalar fields present in the payload; **absent/null
       fields do not overwrite existing non-null values** (events vary in
       completeness). `source = 'webhook'`.
     - Status from EventType for terminal states: `InvoicePaid` → `Paid`
       + set `paid_date`; `InvoiceVoided` → `Void`. Normalize casing
       (`Open/Approved/Rejected/On Hold/Reviewed/Paid/Void/Disputed`).
     - Line items: only if `Labors`/`Materials` arrays are **non-empty**,
       delete-and-replace for that invoice. Empty arrays (common on
       status-change events) leave existing line items intact.
  3. Append `invoice_status_history`.
  4. **Sync to `work_orders` (§7).**
  5. Mark event `processed`. On any exception → `dead_letter` + store
     error; continue (one poison event must not block the queue, and must
     not crash the worker).

### 5.3 Logging & alerts (structlog)

- Log each receipt: `{event_type, object_id, signature_valid, dedupe_hit}`.
  Never log the signing key or full raw body at info level.
- Alert when (reuse the Resend path from `app/services/email.py`): an
  `invalid_signature` row appears in **production**, dead-letter count > 0,
  or no production events for > 7 days (possible disabled webhook — check
  Provider Automation).

---

## 6. (deferred) — see §7 for the integration that replaces this

## 7. Integration with `work_orders` (the payoff)

This is what turns an invoice store into the Phase 1.5 read-back loop.

- **Match:** `invoices.wo_tracking_number == work_orders.sc_work_order_id`
  (both numeric), or by `invoice_number == work_orders.sc_invoice_number`
  once we start submitting (§ the submit spec in `servicechannel-api.md`).
- **New `work_orders` columns** (one Alembic migration; mirror the
  existing `brenk_*` pattern): `sc_invoice_id`, `sc_invoice_number`,
  `sc_invoice_status`, `sc_invoice_submitted_at`, `sc_invoice_last_error`.
- **Drive the pipeline from events:**
  - `InvoiceCreated/Open` → set `sc_invoice_status='Open'`,
    `sc_invoice_submitted_at`.
  - `InvoiceApproved` → `sc_invoice_status='Approved'`.
  - `InvoicePaid` → set an SC-derived paid timestamp. **Decision:** keep
    `brenk_paid_at` as the manual override (per the existing CLAUDE.md
    rule) and add `sc_paid_at`; the `/invoices` "Paid" tab treats either
    as paid. (Or, simplest v1: if `brenk_paid_at` is null, set it from
    `PaidDate`.) Pick during build with Charles.
  - `InvoiceRejected` → `sc_invoice_status='Rejected'` +
    `sc_invoice_last_error`; surface a "Resubmit" affordance.
- **Net effect:** the `/invoices` tabs (Sent → Paid) become SC-driven, and
  the manual "Mark paid" button becomes an override rather than the only
  signal — closing the loop the blocked OData read was meant to close.

---

## 8. Backfill (one-time) — `backend/scripts/backfill_invoices.py`

History can't come from the API (read blocked), so it comes from UI
exports. Run **after** the webhook is Active (the merge rule resolves the
overlap).

- **[HUMAN]** Production Provider Automation → Invoices module → export
  (Excel/CSV), all subscribers/statuses, full date range (slice by year
  if the UI caps export). Drop into `backfill/input/` (gitignored).
- **Script** (`--env=production backfill/input/*.xlsx`, add `openpyxl`):
  - Header-mapping config (canonical field → candidate header names). On
    first run, print detected mapping + unmapped columns and **halt for
    confirmation** (`--yes` to skip) — SC export headers are undocumented;
    don't guess silently.
  - Normalize: trim, US dates `MM/DD/YYYY`, currency `$1,234.56`→number,
    status casing per §5.2.
  - Upsert with `source='backfill'`, `sc_invoice_id=NULL`, conflict on
    `(sc_env, invoice_number, coalesce(wo_tracking_number,-1))`:
    no row → insert; existing `source='webhook'` → **webhook wins**, only
    fill NULL columns; existing `source='backfill'` → overwrite (idempotent
    re-runs).
  - Line items left empty for backfill rows (UI export lacks them).
  - Summary: read/inserted/merged/skipped + a CSV of parse failures; exit
    non-zero if > 2% fail.

---

## 9. Rollout order

1. Build receiver + worker + models + migration; pass unit/integration
   tests (fixtures from SC's *Event Objects* docs: InvoiceCreated w/
   Labors+Materials, Approved, Rejected, Voided, Open; cover in-order,
   out-of-order, duplicate, empty-arrays-no-wipe, unknown→dead_letter,
   malformed→dead_letter, ping→200-stored-nothing, HMAC self-vector +
   one-byte-mutation-fails).
2. **Sandbox:** tunnel (`cloudflared`/`ngrok` → localhost:8000) → register
   sandbox webhook (Inactive) → Ping → smoke test → Active → create a
   sandbox invoice end-to-end (remember the weekend wipe).
3. Deploy receiver + worker to Fly (already our prod hosts).
4. **Production:** register prod webhook (Inactive) → Ping → Active →
   confirm first real event arrives with a valid signature.
5. Run the production backfill (§8).
6. Wire the three alerts (§5.3).
7. **(Human, parallel)** keep pushing SC support on `GET /v3/odata/invoices`
   read access (Provider `2000091087`). If granted later, add a nightly
   reconciliation poll (`$filter` on recent `UpdatedDate`, follow
   `@odata.nextLink`) as a strictly-additive hardening step — webhooks
   stay primary.

---

## 10. Acceptance criteria

**Receiver/worker:** 200 in <5 s, raw body persisted byte-exact; HMAC on
raw bytes, constant-time; bad sig + non-empty → 401 + `invalid_signature`;
ping → 200; duplicate → single row, single processing; out-of-order does
not regress state; empty `Labors`/`Materials` leaves line items intact;
poison event → dead-lettered, queue continues; all 12 invoice event types
route; `InvoicePaid`/`InvoiceVoided` set terminal state from EventType;
sandbox end-to-end row appears within ~30 s; sandbox/prod separate
deployments + signing keys.

**Integration:** an `InvoicePaid` for a known WO flips that WO to the Paid
tab; a rejected invoice surfaces its reason.

**Backfill:** idempotent re-runs; overlapping slices don't duplicate; a
backfill row later adopted by a webhook event (gains `sc_invoice_id`,
`source`→`webhook`); currency/date parsing verified on ≥5 real rows;
failure CSV produced; exits non-zero if >2% fail.

---

## 11. Verify before / during build

- Confirm SC's exact header names (`Sign-Type`, `Sign-Data`) and that the
  HMAC is over the raw body keyed by the signing-key **text** — matches
  our existing "Webhooks — full spec" notes, but re-check against the live
  *Webhooks* guide before coding.
- Confirm the invoice `EventType` catalog (the 12 above) against SC's
  *Event Objects* page; add any we're missing as no-op routes.
- Decide the `brenk_paid_at` vs `sc_paid_at` model with Charles (§7).
- Decide endpoint placement: `/api/v1/webhooks/servicechannel` (chosen)
  vs a top-level `/webhooks/...`. Either is fine; keep it auth-exempt.

---

## 12. Resume point — start here next session

Nothing webhook-related is coded yet; this doc + the verified Phase 1.5
findings are the whole state. The work itself has NOT started. First
slice, in order:

1. **Schema first.** Add the 5 SQLAlchemy models (§4) +
   `alembic revision --autogenerate` (surrogate `id` PK + the two unique
   indexes; enable RLS in the migration). Apply to dev.
2. **Receiver endpoint** `POST /api/v1/webhooks/servicechannel` (§5.1):
   raw-body read, HMAC verify (`hmac.compare_digest`), dedupe insert,
   `defer` the worker job, 200. Auth-exempt. Unit-test the HMAC with a
   self-vector + one-byte-mutation, and the ping/empty-body → 200 path.
   **No worker logic yet** — just store the raw event.
3. **Worker task** (§5.2) + the `work_orders` integration (§7) +
   status-history, tested against SC sample-payload fixtures.
4. **Then** the human SC setup (§2), tunnel smoke test (§9), and backfill
   (§8).

Blockers/inputs needed before going live (not before coding): CJ copies
`SC_WEBHOOK_SIGNING_KEY` from the sandbox WebHooks page; decide the
`brenk_paid_at` vs `sc_paid_at` model (§7) with Charles. None of these
block starting steps 1–3 against fixtures.

Separately, this is unrelated to the **submit** path (which is already
verified buildable — see `servicechannel-api.md` "Spike results
2026-06-10"). Submit and webhook-read-back are two independent Phase 1.5
pieces; either can be built first.
