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
