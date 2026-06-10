# Production Deployment Runbook

How to deploy, redeploy, and operate the production Brenk Operating
Platform. Original cutover happened 2026-05-27 — this captures the
steady-state ops, not the one-time bring-up.

## Production topology

| Surface | Where | Notes |
|---|---|---|
| Backend API | Fly.io app `brenk-platform-web` | 2 machines, `dfw` region, `/health` probe |
| Worker | Fly.io app `brenk-platform-worker` | 1 machine, hourly WO sync via Procrastinate |
| Frontend | Vercel project `brenk-operating-platform` | linked from `frontend/` directory |
| Database | Supabase project `Brenk Production` | session-mode pooler on `:5432` |
| DNS | GoDaddy | A records → Vercel anycast `76.76.21.21` |

Live URLs:

- Dashboard: https://app.brenkfacilityservices.com/
- Storefront: https://brenkfacilityservices.com/ (also `www.`)
- Backend API: https://brenk-platform-web.fly.dev/
- Backend health: https://brenk-platform-web.fly.dev/health

## Routine deploy: backend

From `backend/`:

```bash
# 1. Make sure local tests pass
pytest

# 2. Commit your changes (Alembic migration included if schema changed)
git add -A && git commit -m "…"

# 3. Push the web app — release_command auto-applies migrations
fly deploy --config fly.web.toml --remote-only

# 4. Push the worker — no migrations, just picks up new task code
fly deploy --config fly.worker.toml --remote-only

# 5. Verify
curl -s https://brenk-platform-web.fly.dev/health
fly logs --app brenk-platform-web --since 2m
fly logs --app brenk-platform-worker --since 2m
```

The `release_command = "alembic upgrade head"` in `fly.web.toml` runs
Alembic before the new image takes traffic. If the migration fails,
the deploy is aborted and the old image stays live — safe by default.

## Routine deploy: frontend

From `frontend/`:

```bash
# 1. Local sanity
npm run lint && npm run build

# 2. Commit
git add -A && git commit -m "…"

# 3. Deploy to prod (NOT the preview channel)
vercel --prod

# 4. Verify
curl -sI https://app.brenkfacilityservices.com/login | head
```

Vercel auto-deploys from `main` on GitHub too if the project is wired
to the repo — `vercel --prod` is the manual override.

## Secrets management

### Fly (backend)

```bash
fly secrets list --app brenk-platform-web
fly secrets set FOO=bar --app brenk-platform-web
```

Source of truth for the full set: `backend/.env.production` (gitignored).
If you rotate a secret in `.env.production`, also push to both Fly apps:

```bash
fly secrets set FOO="$(grep ^FOO= .env.production | cut -d= -f2-)" \
  --app brenk-platform-web
fly secrets set FOO="$(grep ^FOO= .env.production | cut -d= -f2-)" \
  --app brenk-platform-worker
```

### Vercel (frontend)

```bash
vercel env ls production
vercel env add FOO production
```

Vercel doesn't have a `.env.production`-equivalent file you sync from;
add and rotate via the CLI or dashboard. Required vars:

- `NEXT_PUBLIC_API_BASE_URL` — `https://brenk-platform-web.fly.dev`
- `NEXT_PUBLIC_SUPABASE_URL` — `https://vsyfbxdscvbufndhybgj.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — from `backend/.env.production`

## Database migrations

Migrations run automatically on every web deploy via Fly's
`release_command`. To check current head against prod:

```bash
# From your local machine, with .env.production sourced
cd backend
set -a; source .env.production; set +a
alembic current
alembic heads
```

To roll back one migration in an emergency (use sparingly — usually
forward-fix is safer):

```bash
alembic downgrade -1
```

Then redeploy to prevent the next `release_command` from re-applying.

## Procrastinate schema (one-time per database)

Procrastinate maintains its own queue tables outside Alembic. The
**only** time you need to think about this is when standing up a
fresh Supabase project. For the current prod database it's already
applied; for any future project:

```bash
set -a; source .env.production; set +a
procrastinate --app=app.workers.app.procrastinate_app schema --apply
```

If you skip this on a fresh DB, the worker crashes with
`function procrastinate_prune_stalled_workers_v1(double precision)
does not exist`.

## Monitoring + observability

```bash
# Tail logs
fly logs --app brenk-platform-web
fly logs --app brenk-platform-worker

# Machine status
fly status --app brenk-platform-web
fly status --app brenk-platform-worker

# Open a remote shell into the running web container
fly ssh console --app brenk-platform-web

# Live SQL session against prod
set -a; source .env.production; set +a
psql "$DATABASE_URL"
```

Procrastinate job state lives in Postgres:

```sql
-- Active and recent jobs
SELECT id, task_name, status, queue_name, scheduled_at
FROM procrastinate_jobs
ORDER BY id DESC LIMIT 20;

-- Failed jobs
SELECT id, task_name, attempts, scheduled_at
FROM procrastinate_jobs
WHERE status = 'failed';
```

## Common operational tasks

### Force a work-order sync now (don't wait for the hourly tick)

From the dashboard's `/work-orders` page, click "Sync now". Or hit the
API directly:

```bash
curl -X POST https://brenk-platform-web.fly.dev/api/v1/work-orders/sync \
  -H "Authorization: Bearer $JWT"
```

### Force a vendor sync now

```bash
curl -X POST https://brenk-platform-web.fly.dev/api/v1/vendors/sync \
  -H "Authorization: Bearer $JWT"
```

### Restart a Fly app (rare — usually deploys handle this)

```bash
fly apps restart brenk-platform-web
fly apps restart brenk-platform-worker
```

## DNS

A records at GoDaddy:

| Type | Name | Value |
|---|---|---|
| A | @ | `76.76.21.21` |
| A | www | `76.76.21.21` |
| A | app | `76.76.21.21` |

**Don't re-add a `Parked` sentinel** — GoDaddy's parking IPs aren't
Vercel and will break TLS cert issuance + serve a fraction of requests
to the wrong server. The original cutover hit this; deleted and stayed
deleted.

Don't touch the Microsoft 365 / GoDaddy CNAMEs (`autodiscover`,
`email`, `lyncdiscover`, `msoid`, `pay`, `sip`, `_domainconnect`) or
the MX/SRV/TXT records — those belong to Brenk's existing email
infrastructure.

## Disaster recovery

- **Backend down:** check `fly status`, `fly logs`. Re-deploy if needed:
  `fly deploy --config fly.web.toml --remote-only`.
- **Worker down:** same, but `fly.worker.toml`. The hourly SC sync will
  just resume on the next tick.
- **Database corruption / accidental delete:** Supabase Pro has PITR;
  on the Free plan we have daily backups. Restore from the Supabase
  dashboard.
- **DNS broken (e.g. someone re-adds Parked):** see the DNS section
  above. After fixing, give Vercel 5–30 min to re-issue certs.

## Gotchas that bit us during cutover

Captured in CLAUDE.md → "Things To Avoid". Highlights:

1. **Procrastinate `--app` is all dots, not `module:variable`** —
   `app.workers.app.procrastinate_app`.
2. **Editable installs (PEP 660) don't expose nested sub-packages
   to CLI subprocess binaries reliably.** Set `PYTHONPATH=/app` in
   both Fly app `[env]` blocks (already done).
3. **Procrastinate schema must be applied separately from Alembic**
   (see above).
4. **Vercel Deployment Protection** is on by default on Hobby — must
   be disabled at project settings, otherwise every URL is gated
   behind SSO and the public storefront 401s.
5. **DEBUG=true leaks SQLAlchemy echo logs into stdout** — the
   vendor export script needs DEBUG unset/false or its output gets
   contaminated.
