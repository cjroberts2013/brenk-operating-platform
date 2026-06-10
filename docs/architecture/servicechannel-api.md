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

**`POST /invoices` — not attempted (2026-05-25).** Sandbox data is
real-shaped (per CLAUDE.md confidentiality note) and creating a test
invoice would muddy CubeSmart's actual SC state. Holding until we either:

1. Find an SC test-WO Daryl agrees to use as a guinea pig, or
2. Get the documented JSON schema for the POST body from SC support
   without trial-and-error.

> **Update 2026-06-10:** both resolved. We probed `POST /v3/invoices`
> *safely* (a bogus, nonexistent WoIdentifier so nothing could be
> created) purely to read the error class, and got the full payload
> schema from SC's developer guide. **Write scope is confirmed.** See
> "Spike results — 2026-06-10" just below.

### Spike results — 2026-06-10 (write scope CONFIRMED + full payload)

Re-ran the reads and ran the write-scope check via the new re-runnable
script `backend/scripts/probe_sc_invoices.py`, and read the full SC
developer guide (developer.servicechannel.com/guides/invoices).

**Write scope CONFIRMED (sandbox).** `POST /v3/invoices` with a bogus
`WoIdentifier` ("000000000") returned **`400 {"ErrorCode":917,
"ErrorMessage":"Invalid Tracking Number"}`** — a content/validation
error, NOT the `401`/code-504 "security permissions" error. SC
authorized the write and only rejected the deliberately-nonexistent WO.
So our partner-API password-grant token **can POST invoices**; the
invoice push itself is *not* blocked. (Sandbox only; confirm prod scope
separately before shipping, since prod is a different SC app with its own
permission config.)

Follow-up with a **real WO** (351182931) plus a deliberately-bad invoice
number (a dash, to make creation impossible) returned **`400 code 1180
"Invoice Number is not correct: Only alphanumeric characters are
allowed"`**, i.e. it got *past* tracking-number validation to the
number-format gate. So a real WO is accepted and the `^\w*$` rule is
enforced exactly as the config says. The only things between us and a
`201 Created` are a valid alphanumeric `InvoiceNumber`, `InvoiceText`
(resolution), and `InvoiceTotal` <= NTE. We have NOT created a real
invoice (SC invoices are only voidable via the UI); that needs a
throwaway/test WO Daryl blesses.

**Read retest unchanged.** `InvoiceRequirements` / `InvoiceRejectionReasons`
/ `statistics` still ✓. `GET /v3/odata/invoices` still **401 code 504
"security permissions"** — the auto-derive-paid sync is now the ONLY
gated piece. The manual "Mark paid" button stays until that read scope
is granted.

**Eligibility (from the guide's About Invoices):** an invoice can be
created only when WO status is **Completed or Completed/Confirmed** —
exactly our `ready_to_invoice` stage. The Invoices queue's "Ready to
mark up" + "Marked up" tabs are precisely the SC-eligible WOs.

**Two invoice types (subscriber-configured):** **Standard** (labor /
travel / material / freight totals, no labor/material breakdown) vs
**Line Item** (same charges plus itemized `Labors[]` / `Materials[]`).

#### POST /v3/invoices — full field reference (SC dev guide, USA path)

```jsonc
{
  "InvoiceNumber": "string",      // REQUIRED, unique
  "WoIdentifier": "string",       // REQUIRED, WO# (sc_number)
  "InvoiceText": "string",        // resolution; REQUIRED if subscriber RequireResolutionText
  "InvoiceTotal": 0,              // REQUIRED; must be <= WO NTE
  "InvoiceTax": 0,                // optional
  "InvoiceAmountsDetails": {
    "LaborAmount": 0,             // = sum(Labors.Amount) when Labors present
    "MaterialAmount": 0,          // = sum(Materials.Amount) when Materials present
    "TravelAmount": 0, "FreightAmount": 0,
    "OtherAmount": 0,
    "OtherDescription": "..."     // enum: Discount | Management Fee | Markup |
                                  //   Overhead & Profit | Rental Fee |
                                  //   Subcontractor Cost | Shipping & Handling
  },
  // Line Item only — itemized arrays:
  "Labors": [
    { "SkillLevel": "1|2|3",      // 1 Supervisor, 2 Technician, 3 Helper
      "LaborType": "1|2|3",       // 1 Regular, 2 Overtime, 3 Double time
      "NumOfTech": "n", "HourlyRate": 0, "Hours": 0, "Amount": 0 }
  ],
  "Materials": [
    { "Description": "str(<=100)", "PartNum": "str", "UnitType": "1..7",
      "UnitPrice": 0, "Quantity": 0, "Amount": 0 }
  ]
}
```
Non-US/Canada additionally requires `InvoiceTaxesDetails`
(Labor/Material/Travel/Freight/OtherTax); Canada adds `Tax2Details`
(Tax2Amount, Tax2Name: VAT/HST/PST/QST). Brenk is USA — neither needed.
Response: **201 Created** with `{"Id": <newInvoiceId>}`.

#### CubeSmart's live InvoiceRequirements (subscriber 2014917186, pulled 2026-06-10)

| Setting | Value | Implication |
|---|---|---|
| `RequireResolutionText` | **true** | `InvoiceText` required; block submit if `work_orders.resolution` empty. |
| Number `Pattern` | **`^\w*$`** (Alphanumeric Only) | Letters/digits/underscore only — **no dashes/spaces**. e.g. `BRENK12345`, not `BRENK-12345`. |
| `ReuseInvoiceNumber` | 0 (No) | Numbers must be unique; AutoGenerationType 0 = we generate it. |
| `DaysBeforePostingDate` / `MaxDaysAfterPostingDate` | 1 / 1 | Tight submit window around completion. |
| `IsInvoiceNegativeFeatureEnabled` | false | Positives only (markup helper enforces). |
| `IsProviderAbleToAddSalesTax` | true | May set `InvoiceTax` if needed. |
| `LaborCategoryIds` / `MaterialsCategoryIds` | `[10188,10191,10192,10193,10194,11454,13583]` | WOs whose SC category is in these lists **require a Line Item** invoice; others can be Standard. Type selection is per-WO. |

#### Brenk mapping notes
- Vendor cost + markup % are **confidential** and never sent. We submit
  the **marked-up, client-facing** `InvoiceTotal` and the marked-up
  `LaborAmount`/`MaterialAmount` split. Do NOT itemize via
  `OtherDescription: "Markup"`/`"Subcontractor Cost"` (exposes margin).
- **Line-item wrinkle (confirmed with a real WO):** sandbox WO
  `351182931` is `COMPLETED/CONFIRMED`, NTE `$250`, `sc_category_id =
  10192` — which is in CubeSmart's `LaborCategoryIds` AND
  `MaterialsCategoryIds`, so it **requires a Line Item invoice** with
  itemized `Labors[]` and `Materials[]`. A Standard totals-only body
  would be rejected. Brenk pays subs a flat amount and doesn't track
  tech hours/rates, so we need a convention (e.g. one labor line: 1
  tech, 1 hr, `HourlyRate` = marked-up labor) or to confirm with Daryl
  which of these categories he actually invoices.

#### Worked Line Item payload (the body we validated, did NOT submit)

For a category-gated WO like `351182931`, the submit body looks like:

```jsonc
{
  "InvoiceNumber": "BRENK<unique alphanumeric>",   // ^\w*$, unique
  "WoIdentifier": "351182931",
  "InvoiceText": "<resolution text>",              // required
  "InvoiceTotal": 100,                             // <= NTE (250)
  "InvoiceTax": 0,
  "InvoiceAmountsDetails": { "LaborAmount": 60, "MaterialAmount": 40 },
  "Labors":    [{ "SkillLevel":"2","LaborType":"1","NumOfTech":"1","HourlyRate":60,"Hours":1,"Amount":60 }],
  "Materials": [{ "Description":"...","PartNum":"...","UnitType":"1","UnitPrice":40,"Quantity":1,"Amount":40 }]
}
```
Constraints verified against the docs/config: `sum(Labors.Amount) ==
LaborAmount`, `sum(Materials.Amount) == MaterialAmount`,
`LaborAmount + MaterialAmount + ... + InvoiceTax == InvoiceTotal`,
`InvoiceTotal <= NTE`, number matches `^\w*$` and is unique.

**Live create intentionally NOT performed (2026-06-10).** We validated
the write path to the field level (authorized; real WO accepted; number
rule enforced) but deliberately did not POST a fully-valid body, because
SC invoices can only be voided via the web portal, not the API, so a
test invoice would linger in CubeSmart's sandbox state. The path is
proven enough to build against; an actual `201` can wait for the real
feature (or a throwaway test WO).

**Net Phase 1.5 status:** the submit path is fully specced AND
write-authorized (sandbox). The only remaining gate is the
`/v3/odata/invoices` READ scope for auto-paid sync. Re-runnable probe:
`python backend/scripts/probe_sc_invoices.py .env 2014917186 [post]`.

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

### Auto-sync architecture — webhook-driven (revised 2026-05-25)

> **Build spec (2026-06-10):** the sections below are the research that
> fed it; the implementation-ready spec lives in
> `docs/architecture/sc-invoice-webhook-sync.md` (receiver + Procrastinate
> worker + schema + `work_orders` integration + backfill + rollout). Start
> there when implementing.

Original plan was hourly polling of `/v3/odata/invoices`. Then
Charles found SC's **Integration → WebHooks** admin page, which
explicitly says: *"Webhooks allow you to receive notifications
from ServiceChannel regarding Work Orders, Invoices, Proposals
and more."*

Webhooks beat polling here on every axis: real-time vs hourly,
zero load on SC's OData (which is blocked anyway), and SC handles
retries on receiver failure as standard. They also probably
sidestep the OData 401 entirely — webhooks are a separate
permission path.

**Revised plan:**

1. New endpoint `POST /api/v1/webhooks/sc/invoices` (no auth dep —
   webhook signature verifies authenticity instead of JWT).
2. Signature verification middleware (HMAC / bearer / IP allowlist
   — exact mechanism TBD pending the SC webhook docs).
3. Per-event handlers. Likely event types (confirm from SC docs):
   - `InvoiceCreated` / similar → update `sc_invoice_id`,
     `sc_invoice_status = "Open"`.
   - `InvoiceApproved` → set `sc_invoice_status = "Approved"`.
   - `InvoicePaid` → set `brenk_paid_at` to the event's paid date.
   - `InvoiceRejected` → set `sc_invoice_last_error` to the
     rejection reason; UI surfaces a "Resubmit" button.
4. Reconciliation: find the local WO by either
   `WoTrackingNumber == sc_work_order_id` or
   `Number == sc_invoice_number`.

Hourly polling stays in the docs as a fallback path in case the
webhook proves unreachable or unreliable in practice.

**Practical note on testing webhooks in dev:**

Webhooks need a public HTTPS URL. Local dev on `localhost:8000`
can't receive them. Two options:

- **Defer webhook end-to-end testing until production deploy**
  (Fly.io URL is public over HTTPS).
- **Use an ngrok / Cloudflare tunnel** for dev-time receiver
  testing.

We can still implement the receiver endpoint + handlers in dev
without real webhook deliveries — unit-test against fixtures
that mirror SC's payload shape.

### Webhooks — full spec (2026-05-25)

Sourced from <https://developer.servicechannel.com/guides/wh/>.
This is the canonical reference for the read-back side of Phase 1.5.

#### Event delivery

- **Method:** `POST` to the configured URL.
- **Body shape:**
  ```json
  {
    "Object": { /* full object — invoice, WO, etc. */ },
    "EventType": "InvoicePaid"
  }
  ```
  Full object included; no follow-up GET needed.
- **Headers:**
  - `Content-Type: application/json; charset=utf-8`
  - `Content-Length: <size>`
  - `Sign-Type: HMACSHA256`
  - `Sign-Data: <base64-encoded HMAC-SHA256 of body, using signing key>`
- **Required response:** any 2xx within **5 seconds**.
- **Retry:** non-2xx or timeout triggers 3 retries with **5-minute
  delay** between attempts. Total window ~15 min, then event is
  dropped.
- **Circuit-breaker:** after 1000 consecutive failures the webhook
  is paused for 12 hours; further failures permanently disable it.

#### Signature verification

1. Once, after creating the webhook, fetch the signing key:
   `GET /v3/NotificationSubscriptions/SigningKey` (unique per
   subscriber/provider). Stash in `.env` as `SC_WEBHOOK_SIGNING_KEY`.
2. On each inbound POST, compute
   `base64(HMAC-SHA256(raw_body, SC_WEBHOOK_SIGNING_KEY))`.
3. Constant-time compare to the `Sign-Data` header. Reject mismatch
   with 401.

#### Configuration model

| Concept | What it is |
|---|---|
| **Webhook** | The container. Holds the URL + name + enabled flag + 1-20 subscriptions. |
| **Subscription** | A filter inside a webhook. Each subscription targets one object type and a list of event types. Optional `Rules` filter on `Trades` and `Categories`. |

Limits: 20 webhooks per provider, 20 subscriptions per webhook,
400 subscriptions total. We need ~1 webhook with 1-2 subscriptions
for v1 — comfortably under the cap.

Created via `POST /v3/NotificationWebHooks` or via the SC web UI's
**Integration → WebHooks** page. UI is simpler for a one-time
setup; API is for self-service / programmatic re-config.

#### UI form fields (Integration → WebHooks → Add Webhook)

The web UI for creating a webhook exposes everything we need
without touching the API:

- **Signing Key** (at top of page): Show / Copy / Regenerate
  buttons. Self-service — we don't have to call `GET
  /v3/NotificationSubscriptions/SigningKey` programmatically.
  Copy this into `backend/.env` as `SC_WEBHOOK_SIGNING_KEY`
  once we're ready to build the receiver.
- **Name + Description + URL**: the basics.
- **Status**: Active / Inactive radio. New webhooks default to
  Inactive — switch to Active once Ping URL succeeds.
- **Ping URL button**: test connectivity before saving. Use this
  post-deploy to confirm SC can reach our endpoint without
  committing to a subscription yet. Eliminates "is the webhook
  even firing?" guesswork.
- **Add Subscription**: per-subscription form with Object Type
  dropdown (Work Order, Check In/Out, **Invoice**, Proposal,
  Private Network Invitation, ServiceProvider/Contract,
  Checklist), Name, and two filter buttons:
  - **Add / Remove Categories** → `Rules.Categories` in the API
  - **Add / Remove Statuses** → likely subscribe-on-specific-
    status (so we can narrow Invoice subs to status transitions
    we actually care about — confirm shape when we configure)

No permission/role gate visible on the Object Type dropdown,
including Invoice. Reassuring evidence that Brenk's account
can in fact subscribe to invoice events from the UI.

Example registration body:
```json
{
  "Name": "Brenk Operating Platform",
  "Description": "Production invoice + WO state sync",
  "Url": "https://app.brenkfacilityservices.com/api/v1/webhooks/sc",
  "Enabled": true,
  "Subscriptions": [
    {
      "Name": "Invoices",
      "EventTypes": [
        "InvoiceCreated", "InvoiceApproved", "InvoicePaid",
        "InvoiceOnHold", "InvoiceRejected", "InvoiceVoided"
      ],
      "Rules": {}
    }
  ]
}
```

#### Event catalog — what we'd subscribe to (v1)

**Invoice events (auto-sync for Phase 1.5 read-back):**

| Event | Effect on our DB |
|---|---|
| `InvoiceCreated` | Confirm submission landed. Update `sc_invoice_id` + status. |
| `InvoiceOpen` | Provisional submitted state. |
| `InvoiceApproved` | Client approved. Move WO to "Sent · Approved (awaiting payment)" visual. |
| `InvoiceOnHold` | Client paused review. Surface to operator. |
| `InvoiceRejected` | Failed. Set `sc_invoice_last_error`, bounce WO back to "Marked up" with Resubmit button. |
| `InvoicePaid` | **The big one.** Set `brenk_paid_at = PaidDate`. WO moves to Paid tab automatically. |
| `InvoiceVoided` | Provider-side void. Surface to operator. |

Events we'd skip in v1: `InvoiceReviewed`, `InvoiceApprovalCodeChanged`,
`InvoiceDisputed`, `InvoiceStarAdded`, `InvoiceStarRemoved` —
either too specific to multi-level workflows or pure UI annotations.

**Work-order events (deferred — replaces our hourly poll later):**

Webhooks could eventually replace our hourly `sync_work_orders`
polling. Useful events when we get there: `WorkOrderCreated`,
`WorkOrderStatusChanged`, `WorkOrderNoteAdded`,
`WorkOrderScheduledDateChanged`, `WorkOrderNteChanged`,
`WorkOrderResolutionCreated`, `WorkOrderResolutionUpdated`.
The resolution events matter for our submit-readiness check
(invoice requires Resolution text). Out of v1 scope; logged for
later.

#### Permission to register webhooks

The docs specify:
- **Subscribers** need *"Super Admin"* secondary role.
- **Providers** (Brenk's side) need *"Provider Automation Admin"*
  access level.

If Daryl's user account (`brenkconstruction@gmail.com`) doesn't
have **Provider Automation Admin**, the registration POST itself
will 401/403. Worth checking the Brenk admin UI for roles before
trying to register. This is **likely the same root cause** as the
401 on `/v3/odata/invoices` — both are gated by similar role-
based permissioning on the user account, not subscriber consent.

#### Practical sequencing

Webhooks need a **public HTTPS URL**. Receiver can be built and
unit-tested in dev against payload fixtures, but live registration
needs a stable public URL. That makes Phase 1.5 webhook work pair
naturally with the production cutover:

1. **Dev (no waiting):** build the receiver endpoint, signature
   verification, per-event handlers. Tested against fixtures.
2. **Production cutover:** deploy backend to Fly.io → get the
   public URL.
3. **Live setup:** UI registers the webhook with the prod URL,
   fetch signing key, paste into prod `.env`.
4. **Test:** submit one real invoice (via prod's `POST /v3/invoices`
   path or by Daryl using SC's UI), confirm we receive
   `InvoiceCreated` → eventually `InvoiceApproved` → `InvoicePaid`,
   confirm WO state in our app updates.

### Once-and-for-all: known IDs from the SC web UI

- Brenk's ProviderId: **`2000091087`** (shown in the footer of
  Brenk's SC admin pages). This is the `VendorId` field on the
  `POST /v3/invoices` payload (was an open question earlier).
- CubeSmart's SubscriberId: **`2014917186`** (from our `clients`
  table).

### SC integration team contact

For any of these self-service permission questions that aren't
covered by an existing admin UI:

**`scintegration@servicechannel.com`**

Source: the Contractor Request Form's instructions explicitly
route signed forms here. More targeted than generic SC support
— this is the team that handles integration setup directly.

### Three-track unblocker picture (2026-05-25)

Phase 1.5 has three distinct permission tracks, with separate
resolution paths. None of them is "wait on SC support" in the
generic sense — each has a specific channel.

| Track | What it unlocks | Mechanism | Channel |
|---|---|---|---|
| **WO-status writes** | Mark WOs complete in SC from our app, post notes back, update schedule dates | Contractor Request Form | Sign + countersign with CubeSmart, email to `scintegration@servicechannel.com` |
| **Invoice POST** | One-click invoice submission from our app | Unknown — **not on the Contractor Request Form** | Separate inquiry to `scintegration@servicechannel.com` |
| **Invoice read-back** | Auto-derive Sent → Approved → Paid (replaces manual "Mark paid") | **Webhooks** (preferred); OData polling is fallback | Configure on Integration → WebHooks page; needs event-type discovery first |

### What the Contractor Request Form covers (2026-05-25)

A PDF, signed by both Brenk and CubeSmart, sent to
`scintegration@servicechannel.com`. Seven yes/no toggles:

1. Allow complete WO directly to billable (`Completed` or
   `Completed - Confirmed`). *Form notes: "Typically Clients
   check No here." Fine — Daryl goes through SC's invoice flow
   so this is moot for our use case.*
2. Allow complete WO to non-billable (`Pending Confirmation`).
   **Useful** — would let our app mark a WO done in SC.
3. Allow update WO to other non-billable statuses (On Site,
   Parts on Order, etc.). **Useful** for keeping SC in sync
   with our pipeline-stage flags.
4. Allow transfer of internal check in/out in lieu of IVR.
   *Optional* — only if CubeSmart doesn't require store-phone
   caller ID.
5. Allow post notes & scheduled date changes from our app.
   **Useful** — note write-back.
6. Allow creating Work Orders via the API. *Rare in Brenk's
   flow*; nice-to-have.
7. Allow setting non-zero NTE on contractor-created WOs. *Only
   matters if #6 is Yes.*

**No line item for invoice creation.** That's a separate ask.

Fields on the form Brenk would fill in:

- Contractor / Representative Name: Daryl Brenk (or Brenk
  Facility Services, LLC)
- Provider ID(s): **`2000091087`**
- Client: CubeSmart
- Subscriber ID(s): **`2014917186`**
- Requested-by-Contractor column: check Yes on #2, #3, #5 at
  minimum; everything else per discussion with Daryl.

This form is worth getting signed now regardless of when we
build Phase 1.5 — once the WO-status writes are enabled, our
pipeline-stage flags can flow back into SC over time, which
keeps SC's view in sync with what Daryl is doing in our app.

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
- ❌ Actual access to `/v3/odata/invoices` (still 401 on 2026-06-10) —
  the one remaining gate, needed only for auto-paid status sync.
- ✅ **Confirmation that our current account permits writes
  (`POST /v3/invoices`) — CONFIRMED 2026-06-10** (returned `400 Invalid
  Tracking Number`, not 401). Our SC user CAN submit invoices in
  sandbox. See "Spike results — 2026-06-10" above. (Confirm prod
  separately before shipping.)

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

### Production probe results (2026-05-30) — NOT FOUND

Ran the queued probes against **live production** SC via
`backend/scripts/probe_sc_assignee.py` (read-only; re-runnable with
`python scripts/probe_sc_assignee.py .env.production`). The
"prod will populate Assignee" hypothesis is **falsified** — the
assignment Daryl sees in the SC web UI is not exposed on any read
surface our app token can reach.

Evidence:

- **REST `/v3/workorders` (list + `/v3/workorders/{id}` detail):**
  no `Assignee` key at all in the payload — not empty, absent.
- **OData `/v3/odata/workorders`:** the `Assignee` field *is* in the
  schema but **empty across the entire prod set**. The decisive query
  `?$filter=Assignee/UserId ne null` returns **0 work orders** (server-
  side filter over all WOs, not a page sample).
- **`Assignee` is a complex type, not a navigation property** — its
  EDM type is `ServiceChannel.Services.Messaging.Workorders.AssigneeUser`
  = `{ UserId: Int32, UserName: String }`. That's why `$expand=Assignee`
  400s ("Could not find a property named Assignee" as a nav). It comes
  back inline via `$select`, just unpopulated.
- **`/v3/odata/employees`:** 404 — the collection does not exist in
  production (the May 21 notes guessed it did; it doesn't).
- **`/v3/odata/users` has no WorkOrders relation** — `$expand=WorkOrders`
  400s. User rows do carry `DashboardAssigned`, `Roles`, `Permissions`,
  `Access`, `FeedRole`, `SubscriberId` — user-level config, no per-WO
  assignment link.
- **Provider path is the *account* relationship, not employee-level.**
  `$expand=Provider` on a WO hydrates fine but returns **Brenk itself**
  (the servicing provider on CubeSmart's account) on every WO — not the
  sub-vendor and not a named tech. The `GetProviderAssignments` OData
  function exists but returns **0 rows**; `providerassignment` as a
  direct entity set is 404. `ProviderAssignment` models CubeSmart's
  trade/location → provider routing, not Brenk's internal tech
  assignment.

**Conclusion:** there is no readable employee→WO mapping for Brenk's
account. Two reasons are consistent with the data: (a) Brenk never
writes a named SC `Assignee` (Daryl "self-assigns" may mean accepting
the WO as the provider, which lands in `Provider`/acceptance state, not
`Assignee`), or (b) the web UI reads an internal, non-public endpoint
our OAuth scope can't see.

**Only remaining read avenue** is doc probe #4 — open the SC web UI
with browser devtools, click an employee's assigned-WO view, and copy
whatever URL the UI calls. That requires an interactive SC portal
login (Charles), so it's parked until we're in the portal anyway; it
may also turn out to be an internal endpoint we can't authenticate
against.

**Decision:** stop pursuing this as a *read* feature for now. The
"Tech-assigned in SC" cross-reference panel is **shelved** — Brenk-
native vendor assignment (our DB) stays the single source of truth on
the vendor detail page. If Daryl specifically wants SC-side assignment
visibility later, the realistic path is the **write-back** branch
(Phase 1.5): we PATCH `Assignee` from our app so the field we read is
the field we wrote. That's gated on the same `/v3/workorders/{id}`
write investigation as the rest of Phase 1.5.

### Deep dive #2 (2026-05-30) — it's the Sub-Contractors tab, and it's portal-internal

Daryl sent a screenshot of the actual SC portal page that shows the
mapping: the provider portal's **Sub-Contractors** tab (sibling to an
empty **Employees** tab). Each sub-contractor row has an "ASSIGN WO"
button with a count badge, and expanding one reveals "Work Orders
Currently Assigned" listing WO tracking numbers (TN#), store IDs, and
trade. Top of page: "WOs: 0 UNASSIGNED / 15 ASSIGNED".

Key correction to deep-dive #1: this is **sub-contractor assignment**,
not SC "employee/Assignee" assignment. The sub-contractors are SC
**user** accounts Brenk created under its own provider
(`admin+N@brenkfacilityservices.com`, `UserType = Corporate`). We
mapped them: Mario (GTY) = UserId `7197521`, Javier Aboytes = `6071813`,
Larry Marshall = `6057515`, etc. (29 users total, 27 are subs).

Reverse-engineered from Mario's three known-assigned WOs (TN#
349845852, 349767724, 347581885 — TN# == both `Number` and `Id`):

- **The assignment is on a separate resource, NOT the work order.**
  Recursively searched each WO's full OData + REST payload for Mario's
  UserId / name / email / "GTY" → **zero hits**. `Assignee` is `None`
  on all three (consistent with the full-set `Assignee/UserId ne null`
  = 0 from deep-dive #1).
- **Not in notes or work activities.** `workorders({id})/workactivities`
  = 0 rows. The 6 notes are all SC↔Brenk dispatch + store chatter
  (`SystemNote`/`UsersNote`), none referencing the sub. So we can't
  derive assignment from the notes we already sync.
- **Not in any sibling collection.** `trucks` = 0 rows.
  `GetProviderAssignments` = 0 rows (tried bare, `$top`, `$expand`).
  `providerassignment` entity set = 404. `LinkedWorkOrders` /
  `LinkedInWorkOrders` on the assigned WO = both empty (so it's not
  modeled as a subcontracted child WO either).
- **Users aren't queryable for it.** `users(7197521)` by key → 500
  ("Multiple actions" — routing collision with the `scimusers`
  function import). No WO navigation property on `User`
  (`$expand=WorkOrders` etc. all error).
- **REST filter params are ignored.** `/v3/workorders?assignedTo=…`
  (and `userId`/`technicianId`/`subcontractorId`/`assignedUserId`)
  return the same unfiltered default page — the params are silently
  dropped, no assignment filter exists.

Full OData entity-set inventory for the record: `assets, workorders,
rfps, locations, trades, invoices, InvoiceLabor, InvoiceMaterial,
InvoiceTravel, InvoiceOther, notes, attachments, workactivities,
proposals, providerassignment, GetProviderAssignments, MliUserInfo,
MlpUserInfo, users, providers, detailedProviders, subscribers, trucks,
weatherEvents`. None expose sub→WO assignment with data in them.

**Conclusion:** the Sub-Contractors "ASSIGN WO" feature is a
**provider-portal-internal** capability. Its data is not in the public
v3 API (REST or OData) on `api.servicechannel.com`. The portal page
must call a different (internal) endpoint.

**The one definitive remaining step** — capture the network request the
portal fires when it renders "Work Orders Currently Assigned" for a
sub. Whatever URL that is, it returns this data by definition. Pending:
Charles to grab it from DevTools → Network (XHR/Fetch) while expanding a
sub-contractor in the portal, and paste the request URL + response
shape. If it lives on `api.servicechannel.com` and accepts our OAuth
token, we can replicate it; if it's an internal portal endpoint with
cookie/session auth, reading it programmatically is likely off the
table and we'd fall back to the write-back branch above.

Re-runnable probes for all of the above live in
`backend/scripts/probe_sc_assignee.py` plus the ad-hoc queries captured
in this section.

### FOUND (2026-05-30) — it's a different product: SC Workforce

Charles captured the portal's network call. The Sub-Contractors
"Work Orders Currently Assigned" panel is served by a **separate
ServiceChannel product** — SC **Workforce** (the GPS / mobile
check-in system), not the partner API we integrate with:

```
GET https://workforce.servicechannel.com/api/manager/technician/{technicianId}/dispatchedWOs
```

- **Host / backend:** `workforce.servicechannel.com`, which fronts
  `prod-workforce.azurewebsites.net` (an Azure app). Completely
  separate from `api.servicechannel.com`.
- **Identity is a Workforce `technicianId`, not the SC user id.**
  The captured request used `technicianId = 515425`; the SC user id
  for the corresponding sub is a different number (e.g. Mario =
  `7197521`). There is a distinct technician-identity namespace we
  don't currently have a mapping for.
- **Rich response.** Each dispatched WO carries `TrackingNumber`
  (== WO Number/Id), `StoreId`, `Trade`/`TradeId`, `Category`, a full
  `Location` block (lat/long, address, SubscriberId), `ScheduleDate`,
  `PrimaryStatus`/`ExtendedStatus`, `ProviderId`, **plus GPS/check-in
  fields**: `IsAccessGranted`, `CheckInOutInfos`, `CheckInOutEvents`,
  `BadgePresentedDate`, `FirstScanAvailable`, `QrCodeWorkforceUrl`,
  `IsPreAssigned`.

**Bonus discovery:** those GPS/check-in fields are the **"Vendor
on-site 📍"** lifecycle stage we previously documented as having *no
signal to us* (see the lifecycle table in CLAUDE.md). SC Workforce
access would unlock **two** things at once: the sub→WO assignment
mapping *and* real on-site confirmation.

**The blocker — auth.** Our partner-API OAuth bearer token is
**rejected** by the Workforce host:

```
GET https://workforce.servicechannel.com/api/manager/technician/515425/dispatchedWOs
Authorization: Bearer <our partner-API token>
-> 401 {"Message":"Authorization has been denied for this request."}
```

So Workforce is a different auth realm. The browser reaches it via the
portal session (cookie or a Workforce-issued token from the portal
login), which our client-credentials/password grant against the partner
API does not satisfy. `GET /api/manager/technician/515425` (no
`/dispatchedWOs`) 404s and leaks the Azure backend name, confirming a
distinct app.

**Auth mechanism (confirmed).** The Workforce call carries an
`Authorization: Bearer <token>` header. The token is a **JWE**
(`{"alg":"dir","enc":"A128CBC-HS256","typ":"JWT","cty":"JWT"}`) —
i.e. *encrypted*, not just signed, so it's opaque to us (we can't
read its claims). It's issued by the SC portal SSO (the session also
sets `fx_tickauth` / `fx_ticksess_PRODUCTION` cookies). This is a
different token than our partner-API grant produces, and our
partner-API token is rejected (401, above).

**Confirmed integration shape (replayed a live portal token,
read-only).** With a valid Workforce Bearer token, the whole feature
is reachable and clean:

- `GET /api/manager/technicians` → the full technician roster (24 for
  Brenk). Each record has `TechnicianId`, `TechnicianContractorId`,
  `FirstName`/`LastName`, `Email`, `LoginName`,
  `DispatchedWorkOrders` + `DispatchedWorkOrdersCount` (assignment
  counts inline!), plus GPS/vetting fields (`HasBadge`,
  `BgCheckStatus`, `QrCodeWorkforceUrl`).
- `GET /api/manager/technician/{TechnicianId}/dispatchedWOs` → that
  tech's assigned WOs with `TrackingNumber` (== our WO id), `StoreId`,
  `Trade`, full `Location`, status, **and GPS check-in**
  (`IsAccessGranted`, `CheckInOutEvents`, `BadgePresentedDate`,
  `FirstScanAvailable`).
- **Vendor mapping is by email.** Every technician's `LoginName`/`Email`
  is the `admin+N@brenkfacilityservices.com` address we already sync
  onto our vendor rows, so the join is a trivial case-insensitive email
  match — the same fallback `vendor sync` already uses. (The Workforce
  `TechnicianId`, e.g. Mario = 629450, is a *different* namespace from
  the partner-API SC user id, e.g. Mario = 7197521; email is what
  bridges them. The roster also includes Daryl himself,
  `TechnicianId` 146020.)

**The sole remaining blocker is token issuance.** We need a way to
obtain a Workforce Bearer token from a backend (no interactive
browser). Options, in order of preference:
1. SC provisions **Workforce API access** for our provider account
   (documented token endpoint / client credential). Best case.
2. Our existing SC username/password works against a Workforce-specific
   OAuth/token endpoint we don't yet know. (Do **not** brute-force
   this against prod — ask SC for the endpoint.)
3. Fallback: token-harvest via a headless-browser login (capture the
   Workforce JWE token, then call the JSON API directly). Full design
   in `docs/architecture/sc-workforce-assignment-sync.md`. Build this
   ONLY if SC declines the API ask — it carries ToS, fragility, and
   maintenance risk. Last resort, but designed.

Replaying the user's captured token is **not** an integration path —
it's a short-lived, interactive-login JWE; useful only as the
read-only proof (done) that token issuance is the one and only gap.

**Corroborating signal (2026-06-01):** the partner-API
`GET /v3/api/providers/IsSdiMobileEnabled` returns `{"IsEnabled":
false}` for our provider account. SDI = ServiceChannel's mobile/dispatch
integration — the same family as Workforce. That this flag is off is
consistent with the Workforce 401, and gives the SC ask a concrete
hook: *"IsSdiMobileEnabled is false for our account — is enabling that
(or whatever provisions SDI Mobile / Workforce) what grants the
technician/dispatch API access?"* (Surveyed the rest of the Swagger
Providers + Subscribers groups too — `getbytrade`, `GetProvidersRanking`,
`GetRecent/GetLast`, subscriber `trades`/`rules`/`dashboards`, etc. None
expose sub→WO assignment; they're subscriber-facing lookups or
provider/subscriber admin writes. Workforce remains the only route.)

**Status:** fully located and characterized; integration shape +
vendor mapping known and verified end-to-end against live data.
**Blocked solely on Workforce API token issuance** — a vendor/
permissions question for ServiceChannel. Bundle with the Phase 1.5
SC-permissions ask (invoice push). If unblocked, this delivers **two**
features: the sub→WO assignment cross-reference panel *and* the
"Vendor on-site 📍" GPS stage.

### Second path — partner-API `techniciansAssigned` (permission-gated)

The SC partner-API Swagger documents
`GET /workorders/{workorderId}/techniciansAssigned` —
"Retrieve list of technicians assigned to the specified work order"
(tagged **Subscribers**). This is on the **same partner API our token
already authenticates against** — no separate auth realm. If grantable,
it's the cleaner integration (reuses `ServiceChannelClient`).

Tested 2026-05-30 against known-assigned WOs (Mario's 349845852,
Javier's 343852740 / 339416951) and a recent one:

```
GET /v3/workorders/{id}/techniciansAssigned
-> 401 {"ErrorCodes":[504],"ErrorCode":504,
        "ErrorMessage":"API call rejected by security permissions"}
```

Same `504 / security permissions` gate we hit on `/v3/users`. Note the
endpoint is tagged **Subscribers** (CubeSmart's side).

**Confirmed subscriber-only (2026-06-01).** Re-ran in **sandbox** once
SC's gateway recovered — same `504 "API call rejected by security
permissions"` on every WO (Mario's 349845852 + 4 real sandbox WOs).
So it's *not* a prod-only permission quirk: our **provider** account is
not authorized for this **subscriber**-scoped endpoint in *either*
environment. Treat the partner-API read path as **dead for us** — don't
count on `techniciansAssigned` being grantable to a provider. (The 200
response model still isn't visible to us since we can't get a non-error
response.)

**Net: Workforce API is the only viable read route for Brenk.**

**Path ranking after the 2026-06-01 sandbox confirmation:**
1. **Workforce API** (`/api/manager/technicians` + `/dispatchedWOs`) —
   **the only viable read route.** Confirmed working with a token,
   richer than the alternative (GPS check-in, assignment counts). Blocked
   only on a server-to-server Workforce token-issuance path. *This is the
   primary SC ask.*
2. ~~Partner API `/workorders/{id}/techniciansAssigned`~~ — **dead for
   us.** `504 security-permissions` for our provider account in *both*
   prod and sandbox; it's subscriber-scoped. Mention to SC only as "is
   there any provider-accessible equivalent?", but don't expect it.

The SC conversation should lead with Workforce API access; the
write-path question (can a provider POST a technician/sub assignment via
API?) rides along with it.
