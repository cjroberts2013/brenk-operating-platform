# Architecture Overview

## What This Platform Does

The Brenk Operating Platform is an internal operations system that automates the
day-to-day management of Brenk Facility Services. It integrates ServiceChannel
(incoming work orders), QuickBooks (accounting), and the company's vendor network
into a single AI-augmented dashboard.

The system is being built in five phases. Phase 1 is the foundation: a clean
ServiceChannel integration and a custom dashboard. Subsequent phases add
accounting automation, vendor communication, analytics, and a public website.

## High-Level Architecture

```
+---------------------+        +---------------------------+        +-----------------+
|   ServiceChannel    | <----- |  Brenk Operating Platform | -----> |   QuickBooks    |
|     (v3 REST API)   |        |                           |        |  (Phase 2 API)  |
+---------------------+        |  - FastAPI (web)          |        +-----------------+
                               |  - Procrastinate (worker) |
                               |  - Postgres (Supabase)    |
                               |  - Next.js dashboard      |
                               |  - Anthropic Claude API   |
                               |    (Phase 2+)             |
                               +---------------------------+
                                          ^
                                          |
                                  +----------------+
                                  |   Daryl Brenk  |
                                  |  (single user) |
                                  +----------------+
```

## Process Topology

In production, three independent processes run continuously:

1. **Web (FastAPI)** — Serves the dashboard API. Stateless, horizontally scalable.
   Hosted on Fly.io.

2. **Worker (Procrastinate)** — Picks up background tasks from the Postgres-backed
   queue and executes them. Hosted on Fly.io.

3. **Scheduler (Procrastinate)** — Enqueues recurring sync tasks on a schedule.
   Can be combined with the worker process for simplicity.

Two managed services back them:

- **Supabase Postgres** — primary data store, auth provider, and Procrastinate queue backend.
- **Vercel** — hosts the Next.js dashboard frontend.

## Data Flow (Phase 1)

1. Every 5 minutes, the scheduler enqueues `sync_work_orders`
2. The worker picks it up, authenticates with ServiceChannel, and fetches WOs updated
   in the recent window
3. For each WO, the worker upserts into Postgres and enqueues `sync_work_order_detail`
4. Detail tasks fetch full WO data + notes, store everything, and track status changes
5. The dashboard reads from Postgres directly — no API calls in the request path

## Key Design Decisions

- **Postgres-as-queue (Procrastinate)** instead of Redis. Eliminates one managed
  service and gives transactional consistency between business data and job state.
- **`raw_data` JSONB columns** on every SC-sourced table. Preserves the full
  upstream payload for forward-compatibility and recovery.
- **Denormalized status fields on `work_orders`** for fast filtering. Reference
  tables added only where they earn their keep.
- **All timestamps stored as UTC.** Local conversion happens at display time.
- **Vendor model decoupled from SC's Providers.** Brenk's vendor list may be a
  superset of ServiceChannel's representation.

## Phase Sequencing

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Foundation & ServiceChannel | In progress |
| 2 | QuickBooks Integration | Not started |
| 3 | Vendor Communication | Not started |
| 4 | Intelligence & Analytics | Not started |
| 5 | Public-Facing Website | Not started |

## Further Reading

- [ServiceChannel API Notes](servicechannel-api.md)
- [Database Schema](database-schema.md)
- [Local Development Setup](../runbooks/local-development.md)
