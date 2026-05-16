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
