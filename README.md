<<<<<<< HEAD
# Brenk Operating Platform

A custom operations automation platform for Brenk Facility Services, LLC. Integrates
ServiceChannel (work orders), QuickBooks (accounting), and the company's vendor network
into a single AI-augmented dashboard.

## Status

Phase 1: Foundation & ServiceChannel Integration — **in progress**

## Repository Layout

```
brenk-operating-platform/
├── backend/              # Python + FastAPI backend
│   ├── app/              # Application code
│   ├── scripts/          # One-off scripts and utilities
│   └── tests/            # Test suite
├── frontend/             # Next.js + React dashboard (to be scaffolded)
├── docs/                 # Architecture docs, API samples, runbooks
└── .github/              # CI/CD workflows
```

## Phases

1. **Foundation & ServiceChannel Integration** — automated work order syncing and a custom dashboard
2. **QuickBooks Integration & Invoice Automation** — bill and invoice automation
3. **Vendor Communication Automation** — automated outreach to sub-vendors
4. **Intelligence & Analytics** — profitability and performance dashboards
5. **Public-Facing Business Website** — marketing storefront

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [ServiceChannel API Notes](docs/architecture/servicechannel-api.md)
- [Database Schema](docs/architecture/database-schema.md)
- [Local Development Setup](docs/runbooks/local-development.md)

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Procrastinate
- **Database / Auth / Storage:** Supabase (Postgres)
- **Frontend:** Next.js + React + Tailwind (deployed to Vercel)
- **Hosting:** Fly.io for backend and worker processes
- **AI:** Anthropic Claude API
- **Monitoring:** Sentry

## License

Proprietary. © Brenk Facility Services, LLC.
=======
# brenk-operating-platform
Brenk Facility Maintenance operating platform
>>>>>>> 523a7220c2295fda2a8246b2217a93d13da29aab
