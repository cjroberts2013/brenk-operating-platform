# Database Schema

Current schema is defined in `backend/app/models/work_order.py`. This document
captures the design rationale and what's intentionally not yet modeled.

## Tables

### Reference

- **`trades`** — work types (Roofing, Plumbing, Electrical, etc.). Populated
  lazily as new trades appear in synced WOs.

### Core Entities

- **`clients`** — ServiceChannel subscribers (e.g., CubeSmart).
- **`locations`** — physical sites owned by clients (e.g., a specific store).
- **`vendors`** — sub-vendors Brenk dispatches work to. **Decoupled from
  ServiceChannel** — `sc_provider_id` is nullable to allow Brenk-only vendor
  records that don't exist in SC.

### Work Orders

- **`work_orders`** — the main table. Mirrors SC work orders with Brenk-specific
  metadata (assigned vendor, internal status if needed) layered on.
- **`wo_notes`** — full notes thread, sourced from SC's notes endpoint plus
  internal notes added by Brenk.
- **`wo_status_history`** — every status transition we observe, with source
  attribution. Built up as the sync worker detects changes.

## Design Decisions

### `raw_data` JSONB on every SC-sourced table

Every table that holds SC-sourced records also has a `raw_data jsonb` column
storing the complete upstream payload. This is intentional insurance:

- If SC adds fields we want, we can backfill from `raw_data` without re-fetching
- If we discover we mismodeled a field, we can read the truth from `raw_data`
- Cost is small: 8 WOs/day × ~3KB each = ~9MB/year of JSON

### Denormalized status on `work_orders`

`primary_status` and `extended_status` are stored as columns directly on the
`work_orders` row, not as foreign keys to a `statuses` table. Reasons:

- The set of status combinations is small but enumerable lazily
- Common queries ("show me all IN PROGRESS jobs") become single-table scans
- A `statuses` reference table can be added later only when we need metadata
  per status (e.g., "is terminal?", "counts as billable?")

### Vendor not tied to SC Provider

ServiceChannel's API exposes the prime relationship (CubeSmart → Brenk) but
likely does not represent Brenk's downstream sub-vendors. Our vendor model is
independent so we can manage that data ourselves.

### Status history as append-only log

`wo_status_history` is never updated, only inserted into. Gives us a clean
audit trail and enables future analytics ("average time in IN PROGRESS for
roofing jobs") without complex schema.

## Indexes

Beyond primary keys and FK indexes:

- `work_orders.sc_work_order_id` — unique lookups by SC ID
- `work_orders.primary_status` — dashboard filtering
- `work_orders.sc_updated_date` — incremental sync queries
- `work_orders.scheduled_date` — date-range filtering
- `wo_notes.work_order_id` — fetching all notes for a WO

## Intentionally Not Modeled Yet

- **`statuses` reference table** — see above
- **`attachments`** — endpoint not yet confirmed; will add in Week 2 or 3
- **`users`** — will be added with auth integration in Week 3
- **`sync_log`** — observability table; will add when the worker is built in Week 2
- **`categories`, `priorities`, `problem_codes`** — kept as plain strings on
  `work_orders` for now; promote to reference tables only if dashboards need them

## Data Volume Expectations

Based on Brenk's stated ~8 new WOs/day:

- ~3,000 new WOs/year
- ~30,000 status/note events/year
- Years before Supabase free-tier limits matter
- No partitioning, sharding, or special scale work needed
