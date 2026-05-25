# ServiceChannel API — Implementation Notes

Practical notes captured during Phase 1 API exploration. Reference for the
official docs: <https://developer.servicechannel.com/>

## Environments

| | Sandbox2 | Production |
|---|---|---|
| Login URL | `https://sb2login.servicechannel.com` | `https://login.servicechannel.com` |
| API URL | `https://sb2api.servicechannel.com` | `https://api.servicechannel.com` |
| App limit | 40 requests/min | 300 requests/min |
| Company limit | 80 requests/min | 600 requests/min |

**Sandbox2 contains real-shaped data, including real entity names.** Treat
sandbox responses with the same confidentiality as production data. Do not
commit unscrubbed responses to the repository.

## Authentication

OAuth 2.0 with the **Resource Owner Password Credentials** grant. Our backend
holds Brenk's username/password and exchanges them for tokens.

- Token endpoint: `POST {login_url}/oauth/token`
- `Authorization: Basic <base64(client_id:client_secret)>`
- Body (`application/x-www-form-urlencoded`): `username`, `password`, `grant_type=password`
- Access tokens expire in **600 seconds** (10 minutes)
- Refresh tokens are returned and should be used for renewal
- The token endpoint is rate-limited to **once per 5 seconds per user** — token
  caching is mandatory, not optional

Our implementation: `app/services/servicechannel/auth.py`

## Endpoints (Confirmed Working)

### List work orders
```
GET /v3/workorders
```
Returns a JSON array of work order objects.

**Pagination** is page-based:
- `page` — 1-indexed page number
- `pageSize` — records per page. **Default and maximum is 50.** Passing a
  larger value is silently clamped to 50.

To paginate, increment `page` until SC returns fewer records than `pageSize`
(or an empty array). The endpoint provides no total-count header.

**Filterable fields** (all confirmed via Swagger):
`locationId`, `storeId`, `otherLocationId[]`, `id[]`, `category[]`,
`categoryId[]`, `status[]`, `extendedStatus[]`, `number[]` (starts-with),
`serviceId[]` (starts-with), `priority[]`, `purchaseNumber[]` (starts-with),
`trade[]` (starts-with), `tradeId[]`, `scheduledDate[]`, `expirationDate[]`,
`callDate[]`, plus a `sort` string (syntax not documented in Swagger —
needs experimentation to find direction tokens).

**There is NO `updatedSince` / `updatedFrom` / `modifiedSince` parameter** on
this endpoint. Incremental sync by update time has to happen client-side:
either pull all pages and filter by `UpdatedDate`, or sort by update time
descending and stop pagination once an old record appears.

### Get a single work order
```
GET /v3/workorders/{id}
```
Returns the full work order detail including nested `Subscriber`, `Provider`,
`Location`, `Status`, `Notes` (last + count only), `Attachments` (count only),
and other fields.

### Get work order notes
```
GET /v3/workorders/{id}/notes
```
Returns the full notes thread. Response shape:
```json
{
  "Notes": [...],
  "AllNotesCount": int,
  "UserNotesCount": int,
  "SystemNotesCount": int
}
```
Each note has `NoteType` (`SystemNote`, `UserNote`, etc.), `Visibility` (int
enum, meaning TBD), `Attachments` array (notes can carry attachments),
`IsPinned`, `ActionRequired`, `CreatedBy`, `CompanyName`, and timestamps.

## Endpoints (To Be Resolved)

### Attachments
**Status: no working endpoint found.** Tried during Phase 1 exploration:
- `GET /v3/workorders/{id}/attachments` → `UnsupportedApiVersion`
- `GET /v2/workorders/{id}/attachments` → does not work
- `GET /v1/workorders/{id}/attachments` → does not work
- `GET /workorders/{id}/attachments` (no version) → does not work

What we do know:
- The WO detail response includes `Attachments.Count.Total` and `Attachments.Count.Own`, so attachments exist as a concept
- Individual `Note` objects in the notes endpoint have an `Attachments` array — so some attachments are reachable via the notes endpoint
- `IsAttachmentNote` boolean exists on notes, suggesting note-attached files are the primary delivery mechanism

Action items before Phase 2 (where attachments matter most for invoice parsing):
- Re-check the Swagger UI at `https://developer.servicechannel.com/swagger/ui/index?version=3` for any attachment-related routes we missed (may be under a different resource path)
- Reach out to ServiceChannel support to confirm the correct endpoint or whether attachments are only accessible via notes
- Look for a webhook event for new attachments — may be cleaner than polling anyway

For Phase 1, we can extract attachment metadata from notes (the `Attachments` array on each note record) and store it, even without a way to fetch the actual files yet. Files themselves can wait until the endpoint is resolved.

### Vendor / Provider Listing
TBD — likely under `/v3/providers` or similar. Need to confirm whether SC
exposes Brenk's sub-vendors or only the Brenk → CubeSmart relationship.

### "Updated since" filter
**Confirmed unsupported on `/v3/workorders`** — the Swagger has no such
parameter. Incremental sync filters by `UpdatedDate` client-side.

## Throttling Behavior

ServiceChannel applies **two layers of throttling**:

1. **Request-count throttling.** Hard cap at 300 (prod) / 40 (sandbox) per
   minute per app. Returns `429` with a `Retry-After` header.
2. **Execution-time throttling.** Slow requests trigger throttling factors
   added to the `Retry-After` value. Doesn't reject the current request, but
   advises the client to slow down.

Our client respects `Retry-After` automatically.

## Data Model Quirks

- **Status is two-level.** `Status.Primary` ("IN PROGRESS") and
  `Status.Extended` ("DISPATCH CONFIRMED") together describe the real state.
- **`LocationId` at the top level is unreliable** (observed as `0` even when
  `Location.Id` is populated). Always use the nested `Location.Id`.
- **Every timestamp comes in pairs** — UTC (e.g., `CallDate`) and timezone-
  aware DTO (e.g., `CallDate_DTO`). Store UTC; convert at display.
- **`Notes` on the WO detail is a summary** (last note + count). Use the
  notes endpoint for the full thread.
- **System notes have a sentinel `CreatedBy` of `"."`** for some
  system-generated events. Worth handling in UI.

## Open Questions

- Exact syntax of the `sort` parameter on `/v3/workorders` (direction tokens
  — likely one of `UpdatedDate desc`, `-UpdatedDate`, or `UpdatedDate&direction=desc`).
  Required if we want to short-circuit pagination during incremental sync.
- Where attachment files actually live (pre-signed URLs vs. file IDs)
- How sub-vendors are represented (or whether they're not at all)
- Webhooks: ServiceChannel offers them — could replace polling for some events

## Invoice endpoints — Phase 1.5 anchor (2026-05-22)

SC's `Invoices` API surface (confirmed from Charles's screenshot of the
SC Swagger UI). Documented here so Phase 1.5 — "push invoice line items
to SC" — doesn't start from scratch when we get to it.

### Submit path

These are what we'd wire to a "Submit to ServiceChannel" button on the
"Marked up, ready to send" tab:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/invoices` | **Add an invoice to a WO.** The actual submit. |
| `GET`  | `/invoices/{subscriberId}/InvoiceRequirements` | Per-subscriber config: which fields are required, what GL codes are valid, attachment rules, etc. Call before submit to validate up front. |
| `GET`  | `/invoices/{subscriberId}/OtherChargeOptions/{category}` | Lookup for the "other charges" line-item type (probably parts/misc). |
| `GET`  | `/invoices/{subscriberId}/InvoiceRejectionReasons` | Catalog of possible rejection codes. Pre-load so a failed POST shows a human reason. |

Open: the **payload shape** for `POST /invoices` — we don't know yet
whether it wants one total, or itemized lines (labor / material /
tax / etc.). Our data model already keeps labor + material split, so
either shape is supportable. Probe before designing the UI.

### Read path (state-sync bonus we hadn't planned)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/odata/invoices` | List existing invoices with full state. Folded into our regular sync, this lets us **auto-derive "Sent" → "Approved" → "Paid"** instead of relying on the manual "Mark paid" button. |
| `GET` | `/invoices/{invoiceId}` | Single-invoice detail. |
| `GET` | `/invoices/{invoiceId}/discrepancy` | SC tells us where the submitted invoice differs from approved rates/hours. Drives a "fix this and resubmit" UI. |
| `GET` | `/invoices/{invoiceId}/discrepancyExtended` | Same as above, more detail. |
| `GET` | `/invoices/statistics` | Aggregate stats — could feed a Phase 4 analytics panel. |

If the OData list endpoint carries `Paid` / `PaidDate`, that probably
replaces our `brenk_paid_at` field with a synced value. We keep
`brenk_paid_at` as the manual-override path for cases where Brenk
sees the payment outside of SC.

### Client-side endpoints (Brenk doesn't call these)

| Method | Endpoint | Purpose |
|---|---|---|
| `PUT` | `/invoices/{invoiceId}/reject` | Subscriber rejects (CubeSmart, not Brenk). |
| `PUT` | `/invoices/{invoiceId}/onhold` | Subscriber puts on hold. |
| `PUT` | `/invoices/{invoiceId}/approve` | Subscriber approves. |

We **observe** the state these endpoints produce via the `GET`
endpoints above; we don't ever call them ourselves.

### Ambiguous — need to probe

| Method | Endpoint | Note |
|---|---|---|
| `POST` | `/invoices/{invoiceId}/Payment` | Could be for Brenk to record an inbound payment received from the client. Or could be admin-only. |
| `POST` | `/invoices/Payments` | Batch variant of the above. |
| `POST` | `/invoices/Workorders/{trackingNumber}/Payment` | Same idea keyed by WO. |
| `PATCH` | `/invoices/{invoiceId}/GlCode` | Update GL code post-submission. Useful for the "we got it wrong" flow. |

### Plan for the Phase 1.5 spike (when we get there)

1. **Confirm write scope.** Our current OAuth grant is password-grant
   for reads — verify it lets us hit a POST endpoint, or whether we
   need a different scope/grant.
2. **Probe `POST /invoices` with a real WO.** Send minimal payload,
   see what SC complains about, build up from there. Sandbox first.
3. **Read `InvoiceRequirements` for each Brenk subscriber** Brenk
   actually invoices — likely just CubeSmart in Phase 1. Capture the
   required fields, build the submit payload to match.
4. **Sync `GET /odata/invoices` periodically** to pick up status
   transitions on invoices we've submitted. Decide whether this
   replaces or augments `brenk_paid_at`.
5. **Design the UX:** confirm dialog before POST, error surfacing on
   failure, idempotency guard (`sc_invoiced_at IS NOT NULL` skip).

### Spike results — 2026-05-25

Probed three of the five endpoints listed above. Findings:

**`GET /v3/invoices/{subscriberId}/InvoiceRequirements`** ✓
Returned a full config object for CubeSmart (subscriber `2014917186`).
Highlights for the submit payload:

| Field | Value | Implication for our POST |
|---|---|---|
| `RequireResolutionText` | **true** | Daryl must fill in the WO's Resolution before we can submit. We already capture this from SC (`work_orders.resolution`); UI needs to warn if empty. |
| `RequireApprovalText` | false | Skip. |
| `DaysBeforePostingDate` | 1 | 1-day window before posting date is allowed. |
| `MaxDaysAfterPostingDate` | 1 | 1-day window after posting date. Operationally tight — submit fast. |
| `IsInvoiceNumberValidationFeatureEnabled` | true | SC validates the invoice number format. Need to learn the rule (probe a real invoice, or ask SC support). |
| `IsInvoiceNegativeFeatureEnabled` | false | Negative-amount invoices rejected. Our markup helper enforces positives. |
| `IsInvoiceZeroVATEU` | false | Not EU; ignore. |
| `AvailableTrades` | JSON array | The list of valid `Trade.Id` values CubeSmart accepts on an invoice. Mostly overlaps with our `trades.sc_trade_id` mirror. |

**`GET /v3/invoices/{subscriberId}/InvoiceRejectionReasons`** ✓
Three generic rejection codes: "Work order not invoiceable" (1),
"Invoice requires correction" (2), "Other" (3). Useful for the
failed-submit UI but no surprises.

**`GET /v3/invoices/statistics`** ✓
`{DaysPeriod: 30, WoReadyForInvoices: 16, OpenInvoices: 0,
ApprovedInvoicesDaysPeriod: 3, ApprovedInvoices: 2}` — matches our
dashboard's "Ready to invoice" count (within a recency window).
Could feed a small "SC pipeline health" widget later.

**`GET /v3/odata/invoices`** ✗ **401 "API call rejected by security
permissions" (error code 504).** Same error class we hit on
`/v3/users` (forced us to OData users). Implications:
- We cannot enumerate existing invoices to sample the response shape.
- We cannot poll for invoice state changes (Sent → Approved → Paid)
  without an expanded scope.
- The manual "Mark paid" button in our UI stays, for now. Auto-derive
  is blocked on scope.

**Update 2026-05-25:** the response schema for `/v3/odata/invoices`
was provided by Charles from SC's docs site. The endpoint is still
gated by OAuth scope at runtime, but with the schema in hand we can
build the auto-sync logic now and just point it at the endpoint once
scope is granted. Schema and mapping captured in the next section.

**`POST /invoices` — not attempted.** Sandbox data is real-shaped
(per CLAUDE.md confidentiality note) and creating a test invoice
would muddy CubeSmart's actual SC state. Holding until we either:

1. Find an SC test-WO Daryl agrees to use as a guinea pig, or
2. Get the documented JSON schema for the POST body from SC support
   without trial-and-error.

### Blocked on SC support engagement

To finish the Phase 1.5 spike we need ONE of:

- ~~The full request schema for `POST /v3/invoices`~~ — **OBTAINED
  2026-05-25 from Charles via SC's docs site. Schema captured
  below.**
- Expanded OAuth scope that unlocks `/v3/odata/invoices` — letting
  us GET a sample existing invoice to mirror the shape, AND
  letting us auto-sync invoice state for the Sent → Paid pipeline.

The second is still worth asking SC support for — it unblocks
auto-derive-paid (which would replace the manual Mark paid button)
without needing to wait for client-side state to be visible.

### POST /v3/invoices — request schema

Full schema (2026-05-25, from SC docs):

```jsonc
{
  "InvoiceNumber": "string",            // REQUIRED. Operator-created.
  "InvoiceDate": "2026-05-25T17:51:28Z",
  "InvoiceDateDTO": "2026-05-25T17:51:28Z",
  "WoIdentifier": "string",             // REQUIRED. WO# (sc_number).
  "InvoiceTax": 0,
  "PostedTaxRate": 0,
  "NonTaxableLabor": 0,
  "NonTaxableTravel": 0,
  "NonTaxableMaterial": 0,
  "NonTaxableFreight": 0,
  "NonTaxableOther": 0,
  "WithMismatchedRates": false,
  "InvoiceTotal": 0,
  "InvoiceText": "string",              // CubeSmart-required (resolution).
  "InvoiceAmountsDetails": {
    "LaborAmount": 0,
    "MaterialAmount": 0,
    "TravelAmount": 0,
    "FreightAmount": 0,
    "OtherAmount": 0,
    "OtherDescription": "string"
  },
  "InvoiceTaxesDetails": { /* per-category tax % + amount */ },
  "Tax2Details": { "Tax2Amount": 0, "Tax2Name": "string" },
  "TaxIncluded": { /* per-category EU VAT flag strings */ },
  "Labors":    [ /* optional line items */ ],
  "Materials": [ /* optional, has per-material MarkUpPercent */ ],
  "Travels":   [ /* optional */ ],
  "Others":    [ /* optional */ ],
  "ExplainDispute": "string",
  "SubmitDisputed": false,
  "VendorId": 0,
  "Terms": "string",
  "Attachments": [ /* optional */ ]
}
```

**Note** (from SC docs): the WO must be in `Completed` status for the
POST to succeed. This matches our pipeline — only WOs in our
`ready_to_invoice` stage map to that state, and that's exactly what
the "Marked up, ready to send" tab filters to.

### Our data → SC payload mapping

What we know we'll send for the minimum-viable Brenk submit:

| SC field | Source | Notes |
|---|---|---|
| `InvoiceNumber` | Generated. **TBD** below. | Daryl might already have a numbering scheme in SC. |
| `WoIdentifier` | `work_orders.sc_number` | TrackingNumber/WorkOrderNumber per docs. |
| `InvoiceDate` / `InvoiceDateDTO` | `now()` UTC | Must be within CubeSmart's 1-day posting window per `InvoiceRequirements`. |
| `InvoiceText` | `work_orders.resolution` | **Required by CubeSmart**. If empty we should error before submit. |
| `InvoiceTotal` | `(labor + material) × (1 + markup/100)` | Matches what the markup helper shows today. |
| `InvoiceAmountsDetails.LaborAmount` | `brenk_labor_cost × (1 + markup/100)` | Post-markup billable amount. |
| `InvoiceAmountsDetails.MaterialAmount` | `brenk_material_cost × (1 + markup/100)` | Same. |
| `InvoiceAmountsDetails.TravelAmount` | `0` | Brenk doesn't track travel as a separate cost today. |
| `InvoiceAmountsDetails.FreightAmount` | `0` | Same. |
| `InvoiceAmountsDetails.OtherAmount` | `0` | Same. |
| All `Tax*` fields | `0` | Brenk's WOs in dev are US, no VAT, no posted tax rates. Revisit per-subscriber if CubeSmart actually wants tax detail. |
| `Labors`, `Materials`, `Travels`, `Others` | empty arrays / omitted | Per the docs, optional. The amounts in `InvoiceAmountsDetails` are sufficient unless SC's UI needs the breakdown for audit. |
| `VendorId` | TBD — likely Brenk's provider ID in SC | Different from `assigned_vendor_id` (which is Brenk's sub-vendor). |
| `Terms` | `""` | Skip in v1. |
| `Attachments` | `[]` | Skip in v1. Could ferry vendor receipts later. |

### Open decisions for the implementation

1. **InvoiceNumber format** — Daryl likely has an existing scheme he
   uses in SC. Likely candidates:
   - `BRENK-{wo.sc_number}` — readable, unique per WO. *(default if Daryl has no preference)*
   - `BRENK-{wo.sc_number}-{yyyymmdd}` — if he re-invoices the same WO. Probably overkill.
   - Sequential `BRENK-00001` — needs a counter. Not worth the complexity.
   Will ask Daryl which one he wants.

2. **Auto-submit vs confirmation dialog.** Default: **confirmation
   dialog**. The "Submit to ServiceChannel" button on the WO detail
   (or in the "Marked up, ready to send" row) opens a dialog showing
   the exact JSON we'll send, with a final Submit button. Preserves
   Daryl's review beat. Once he's used it 50 times we can add a
   "skip dialog" preference, but defaulting safe is the right call.

3. **Line items (`Labors`/`Materials`) vs aggregated amounts only.**
   Default: **aggregated amounts only**. We don't capture the
   structured data (hours × rate, part numbers, etc.) that would
   make line items meaningful. SC docs explicitly allow omitting
   them when amounts are sufficient. Revisit if CubeSmart starts
   rejecting amount-only submissions.

4. **Tax handling.** Default: **zero everywhere**. Brenk's sandbox
   data shows no posted tax rates. If CubeSmart wants tax broken
   out we'll see it in rejection reasons or discrepancy responses
   and add it then.

5. **`VendorId` field.** Open — needs probing. Likely Brenk's own
   `ProviderId` in CubeSmart's subscriber context, not the
   `assigned_vendor_id` we track on the WO (which is the
   *sub-vendor* Brenk dispatched). Will probe a known existing
   invoice via discrepancy endpoint (which doesn't need OData
   scope) to confirm.

6. **What we record after submit.**
   - New WO column `sc_invoice_number` — the InvoiceNumber we sent.
   - New WO column `sc_invoice_submitted_at` — UTC timestamp of
     the successful POST.
   - New WO column `sc_invoice_id` — the ID SC returned, if it
     returns one. (Schema doesn't show a response body; need to
     POST once to find out.)
   - On 4xx from SC, record the rejection reason in a new column
     `sc_invoice_last_error` (string, last error message) so
     the UI can surface "Last submit failed: …"

### GET /v3/odata/invoices — response schema + read-back mapping

Response is an array of invoice objects. The fields we care about
for read-back / auto-sync:

| SC field | Type | Maps to our DB | Notes |
|---|---|---|---|
| `Id` | int | `work_orders.sc_invoice_id` | The SC-assigned invoice id. Stable identifier. |
| `Number` | string | `work_orders.sc_invoice_number` | The InvoiceNumber we submitted. Round-trips. |
| `WoTrackingNumber` | int | join to `work_orders.sc_work_order_id` | Links the invoice back to our WO. |
| `Status` | string | derive `brenk_paid_at`, `sc_invoice_last_error` | Values observed in the docs example: `Open`, `Approved`, `Paid`, `Rejected`, others TBD when we sample real data. |
| `PostedDate` | datetime | `work_orders.sc_invoice_submitted_at` (cross-check) | Useful to confirm our local timestamp matches SC's. |
| `ApprovedDate` | datetime (nullable) | (no column yet — add if Daryl wants the distinction) | Set when client approves. |
| `PaidDate` | datetime (nullable) | `work_orders.brenk_paid_at` (when `Status == Paid`) | **Replaces the manual Mark paid button** once auto-sync is live. |
| `UpdatedDate` | datetime | tracking only | For incremental polling: `$filter=UpdatedDate gt {last_sync}`. |
| `InvoiceTotal` | decimal | (no column — already derivable) | Sanity-check our computed total against SC's. |
| `InvoiceBalance` | decimal | (no column) | Outstanding owed. Could feed a future "AR ageing" panel. |
| `Payments[]` | array | (no column) | Itemized payment records (amount, date, paid by). Phase 4 analytics food. |
| `Provider` | nested | (no column) | Brenk's provider record. Confirms what `VendorId` should be in our POST payload. |
| `Subscriber` | nested | (no column) | CubeSmart's info. Mostly redundant with our `clients` table. |

### Status → tab mapping (auto-sync)

Once auto-sync is live, an invoice's `Status` field directly drives
which tab the WO appears in on `/invoices`:

| `Status` | Tab | Brenk-side effect |
|---|---|---|
| `Open` | Sent (just submitted) | Set `sc_invoice_submitted_at`. |
| `Approved` | Sent (client approved, awaiting payment) | No-op; the WO stays in Sent. |
| `Paid` | Paid | Set `brenk_paid_at = PaidDate`. |
| `Rejected` | (back to Marked up?) | Set `sc_invoice_last_error = <reason>`. May need an explicit "Rejected" sub-state to avoid surprises. |
| any | tracking | Always update `sc_invoice_id`, `sc_invoice_number`. |

Open question for when we see real data: what `Status` strings does
SC actually use? The schema example is just `"string"` — real values
TBD on first successful read.

### Auto-sync architecture

When `/v3/odata/invoices` is reachable:

1. New Procrastinate periodic task `sync_invoices` (hourly, like WOs).
2. Query: `GET /v3/odata/invoices?$filter=UpdatedDate gt {max(work_orders.sc_invoice_updated_at)}` — incremental, only changed records.
3. For each invoice, look up the WO by `WoTrackingNumber == sc_work_order_id` (or fall back to matching `Number == sc_invoice_number`).
4. Update the WO's tracking columns + derive `brenk_paid_at` from `PaidDate` when `Status == "Paid"`.
5. On `Status == "Rejected"`, surface the reason on the WO detail; UI gives a "Resubmit" button that reuses the same payload-builder.

Once this is wired the manual "Mark paid" button can become a
fallback only (for the rare case where Brenk records a payment
outside SC).

### Implementation plan

When the go signal lands:

**Submit (POST) — six steps:**

1. **Migration**: add `sc_invoice_number`, `sc_invoice_submitted_at`,
   `sc_invoice_id`, `sc_invoice_status`, `sc_invoice_updated_at`,
   `sc_invoice_last_error` columns to `work_orders`. (Status +
   updated_at are added in this round so the read-back sync below
   can write to them without a follow-up migration.)
2. **SC client method**: `post_invoice(payload: dict) -> dict`
   wrapping the POST + 4xx handling. Also `list_invoices_updated_since(
   ts: datetime) -> list[dict]` wrapping the OData GET.
3. **Payload builder**: pure function `build_invoice_payload(wo) ->
   dict` (testable without a DB or SC). Validates required fields
   (resolution non-empty, markup set, labor+material set, WO in
   COMPLETED status) and raises a clear error otherwise.
4. **New endpoint**: `POST /api/v1/work-orders/{id}/submit-invoice`.
   Body: empty (everything we need is on the WO already). Returns
   the updated WorkOrderDetail with the SC ID populated, or a 4xx
   echoing SC's error. Also writes `sc_invoice_submitted_at` and
   `sc_invoice_status = "Open"` (provisional — will get the real
   value on next read-back sync).
5. **Frontend confirmation dialog**: Opened from a "Submit to
   ServiceChannel" button on the markup helper or on the
   "Marked up, ready to send" tab row. Shows the payload, the
   billable breakdown, the resolution text, and a primary Submit
   button. On success, the WO moves to the "Sent" tab on next
   navigation; on failure, surfaces SC's reason.
6. **Idempotency**: the submit endpoint refuses to post if
   `sc_invoice_number IS NOT NULL` already — guards against
   double-clicks and accidental re-submits.

**Read-back (auto-sync) — three more steps:**

7. **Sync service** `sync_invoices_from_sc()` in
   `app/services/sync/invoices.py`. Mirrors the existing WO sync
   shape. Pulls incremental via `UpdatedDate` filter, joins each
   SC invoice to a local WO by `WoTrackingNumber`, updates the
   tracking columns + the derived `brenk_paid_at`.
8. **Periodic schedule**: hourly via Procrastinate, same as WO sync.
   Manual trigger endpoint `POST /api/v1/invoices/sync` for the
   debug/dev workflow.
9. **UI tweaks**:
   - Vendor-side rejected handling: WO appears in "Marked up" tab
     again with a red "Rejected: <reason>" badge and a "Resubmit"
     button. The Resubmit button re-runs the payload builder
     (which picks up any edits Daryl made since the rejection)
     and POSTs again, this time clearing `sc_invoice_last_error`.
   - Sent-tab subtitle gains an "Approved" sub-state visualization
     once SC bumps Status: `Sent · Approved (awaiting payment)`.
   - The manual "Mark paid" button stays as a fallback but now
     reads as "Mark paid manually (skip waiting for SC sync)" so
     Daryl knows the normal flow is automatic.

After Phase 1.5 ships, the "Marked up, ready to send" tab becomes
genuinely actionable — one click, gone — and the "Paid" transition
becomes automatic via the read-back sync. The manual SC-entry step
disappears entirely; the manual Mark paid button becomes the
exception path rather than the default.

### Current blockers — 2026-05-25

- ✅ POST /v3/invoices request schema — captured.
- ✅ GET /v3/odata/invoices response schema — captured.
- ❌ Actual access to `/v3/odata/invoices` (401 today).
- ❌ Confirmation that our current OAuth grant permits writes
  (`POST /v3/invoices`). Untested.

**Important reframing (2026-05-25 from the SC auth docs at
<https://developer.servicechannel.com/basics/general/authentication/>):**

SC's OAuth implementation **does not use scopes**. The docs are
explicit: two grant types (authorization code + resource-owner
password credentials), no scope concept. Permissions are entirely
tied to **the user account whose credentials are in the password
grant** — not to token-level scopes that we could request.

That means our 401 on `/v3/odata/invoices` is **not a scope problem
we ask SC to grant**. It's a **role / permission problem on the
specific SC user account** whose username + password live in
`backend/.env`'s `SC_USERNAME` / `SC_PASSWORD`. Same user can read
work orders, users, notes, invoice subscriber requirements,
statistics — but cannot read the invoice OData entity-set or POST
invoices, because their SC role doesn't grant those rights.

**Path to unblock — likely no SC support ticket needed:**

1. **Identify which SC user account we're using.** Check
   `backend/.env`'s `SC_USERNAME` — that's the account whose role
   we need to expand.
2. **Have Brenk's SC admin grant that user the relevant SC roles.**
   The exact role names aren't in the public docs; the SC admin UI
   should list available roles. Likely candidates: any role
   carrying "Invoice — Read", "Invoice — Create", or similar
   invoice-management permissions.
3. **Verify by re-probing** — a single curl against
   `/v3/odata/invoices?$top=1` confirms the change took.

Once that's done, we can also retry `POST /v3/invoices` with a
real test WO (with Daryl's go-ahead) to confirm writes work end-
to-end.

**If self-service permission-grant doesn't unblock it** (e.g., the
necessary role doesn't exist at the user level in CubeSmart's
subscriber config), then an SC support ticket becomes the fallback.
But the auth docs strongly suggest this is configurable inside
SC's own role/user management, not something SC support has to
flip on their side.

We can still implement everything above now and gate the actual
HTTP calls behind a feature flag (`SC_INVOICE_WRITES_ENABLED=false`)
or run dry-run, logging the payloads we would have sent, until
the user-role expansion is confirmed.

### Interim alternative (if SC support is slow)

Daryl already opens SC manually via the "Open in ServiceChannel"
button on the WO detail page. The markup helper shows him the exact
total to type into SC's own invoice form. That manual hop is the
de-facto Phase 1 state; Phase 1.5 just removes the typing step.

---

## Research: Employee → assigned WOs mapping (2026-05-21)

Daryl noted that in the SC web UI he can view an employee and see every
work order assigned to that employee. We want this mapping in our
dashboard — on the vendor detail page, alongside our own Brenk-native
assignment, as a cross-reference ("did I tell this person about all the
WOs SC thinks they're on?").

**Current state of our knowledge** (from the May 19 probe):

- The per-WO `Assignee` field returned by `/v3/workorders/{id}` is
  **empty across all 341 sandbox WOs**. That's why we previously
  concluded the data wasn't reachable — but it's almost certainly a
  sandbox-only condition, since the web UI clearly reads it from
  somewhere.
- `/v3/odata/users` (which we use for vendor identity sync) returns
  the user list but no assignment relation. The `/v3/users` non-OData
  variant returns `401` with error code 504 — security-permission
  rejection, not a missing endpoint.
- `/v3/odata/employees` exists as a sibling. We have not yet probed
  it for nested assignment data.

**Next probes to run** (queue for when we hit production):

1. `GET /v3/odata/employees?$expand=WorkOrders` — OData expansion
   syntax; if SC models a nav property here, this returns the list
   inline.
2. `GET /v3/odata/users({id})?$expand=...` — same idea on users.
3. `GET /v3/odata/workorders?$filter=Assignee/Id eq {employee_id}`
   — filter from the WO side if the Assignee complex type is
   reachable.
4. Inspect the network tab of the SC web UI while clicking an
   employee — whatever URL the UI hits is, by definition, reachable.

**If we find it**, integration shape:

- New `vendor.sc_assigned_work_orders` relation (computed on-demand,
  not stored — SC is source of truth).
- Vendor detail page: a "Tech-assigned in SC" panel above (or beside)
  the Brenk-tracked active-WOs list. Distinguish visually so Daryl
  knows which is which.
- No write path. SC owns the assignment; we just read.

**If we don't find it** (likely sandbox-only behavior persists into
prod), this becomes a write-back feature — Daryl assigns in our app,
we PATCH the SC Assignee field. That depends on `/v3/workorders/{id}`
accepting writes, which is a separate Phase 1.5 investigation.
