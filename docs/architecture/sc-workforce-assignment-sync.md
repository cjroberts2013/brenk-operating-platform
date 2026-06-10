# SC Workforce assignment sync (token-harvest fallback)

Design for pulling the sub-contractor to work-order assignment (and
on-site GPS check-in) from SC Workforce when the sanctioned API route
is unavailable.

**Status: design only. Do NOT build yet.** This is the documented
fallback for if/when ServiceChannel declines the Workforce API
permissions ask. See "Recommendation" at the bottom.

Companion read: `docs/architecture/servicechannel-api.md` ->
"FOUND (2026-05-30) - it's a different product: SC Workforce" for how
we located the data and confirmed the auth blocker.

## Background

The sub -> WO assignment Daryl sees in the SC portal lives in SC
**Workforce** (the GPS/dispatch product), not the partner API:

- `GET https://workforce.servicechannel.com/api/manager/technicians`
  returns the technician roster with assignment counts (and inline
  `DispatchedWorkOrders`).
- `GET https://workforce.servicechannel.com/api/manager/technician/{technicianId}/dispatchedWOs`
  returns that technician's assigned WOs, each with `TrackingNumber`
  (== our WO id/number), `StoreId`, `Trade`, full `Location`, status,
  **plus GPS check-in fields** (`IsAccessGranted`, `CheckInOutEvents`,
  `BadgePresentedDate`, `FirstScanAvailable`).

Auth there is a `Bearer` **JWE** (encrypted, opaque) issued by the
portal SSO. Our partner-API OAuth token is rejected (401). A captured
portal token worked end-to-end, proving the only blocker is obtaining
that token from a backend.

Vendor <-> technician join is by email: every technician's
`LoginName`/`Email` is the `admin+N@brenkfacilityservices.com` address
already on our vendor rows.

## Key reframe: token harvest, not HTML scraping

We do NOT scrape pages. The data is already clean JSON behind a token.
So the job is:

1. Drive a headless browser through login **once** to capture the
   Workforce Bearer token.
2. Call the JSON endpoints directly with `httpx` (fast, structured).
3. Cache the token; re-login only when it expires.

The browser exists solely to acquire the token. No DOM parsing.

## Architecture

```
Procrastinate task (hourly, behind the scenes)
  |
  |- 1. Get a valid Workforce token
  |      |- try cached token from DB
  |      \- on miss / 401 -> headless login -> capture token -> cache
  |
  |- 2. Call JSON API with httpx (no browser):
  |      |- GET /api/manager/technicians
  |      \- GET /api/manager/technician/{id}/dispatchedWOs  (per tech)
  |
  |- 3. Map technician -> vendor (admin+N@ email),
  |      TrackingNumber -> work_order
  |
  \- 4. Upsert SC-assignment + GPS fields onto work_orders
        (errors logged, never break the main WO sync)
```

## Login + token caching

The token is opaque (JWE), so we cannot read its expiry. Work around it:

1. **Store** the token in the DB (a small `integration_session` table
   or kv row) with a captured-at timestamp, plus the session cookies
   (`fx_tickauth`, `fx_ticksess_*`).
2. **Reuse** the cached token every run. On a `401` the token has
   expired: trigger a fresh login, capture a new token, cache it,
   retry once.
3. **Login frequency:** ideally one login per token lifetime. If the
   token outlives an hour, hourly syncs reuse it and rarely re-login.
   If shorter, worst case one login per hourly run. Caching also kills
   redundant logins within a run and across "sync now" bursts.
4. **Optional:** persist the session cookies and try re-minting a token
   from them without re-typing credentials; fall back to a full form
   login if the session is dead.

## Token capture (Playwright)

Python Playwright fits the stack. Flow:

1. Launch headless Chromium, open the SC provider portal login.
2. Fill credentials, submit, follow the SSO redirect.
3. Navigate to the Sub-Contractors page (fires a
   `workforce.servicechannel.com/api/...` request) and **intercept that
   request to read its `Authorization: Bearer` header**
   (`page.on("request")`). Reading `sessionStorage` is an alternative
   once we know the storage key.
4. Hand the token to `httpx`, close the browser.

## Environment awareness

Driven by `SC_ENVIRONMENT`, same as the API client:

- Select the portal login URL + Workforce host (prod is
  `workforce.servicechannel.com`; the sandbox equivalent needs
  confirming, and sandbox may not have Workforce data at all).
- Credentials: the portal login likely reuses the `SC_USERNAME` /
  `SC_PASSWORD` we already store per environment (the API password
  grant uses the same user password). **Confirm in the spike.**

## Data model

A WO maps to one dispatched technician, so columns on `work_orders`
are simplest (vs a new table):

- `sc_workforce_technician_id` (int, null)
- `sc_workforce_vendor_id` (FK to vendors, resolved by email)
- GPS / on-site: `sc_onsite_at`, `sc_access_granted` (bool),
  `sc_badge_presented` (bool)

This is a **read-only cross-reference** (SC stays source of truth for
the SC-side assignment), shown alongside our Brenk-native
`assigned_vendor_id`. The GPS fields light up the "Vendor on-site"
lifecycle stage previously documented as no-signal.

## Where it runs + UX

- New Procrastinate periodic task (`sync_workforce_assignments`),
  hourly or chained after the existing WO sync. Behind the scenes; the
  existing "Sync now" button can include it.
- **Fail-safe:** wrap so any login/scrape error logs and exits cleanly
  without touching the WO sync. Critical given the fragility below.
- Dashboard: a "Tech assigned in SC" panel on the vendor detail page,
  and the "Vendor on-site" stage on WO detail.

## Implementation phases

1. **Spike (half a day, the real gate):** confirm headless login works
   for our account, capture a token, confirm which credentials the
   portal wants, check for MFA / CAPTCHA / bot-detection.
2. **Token + API module:** login/capture/cache + the two API calls +
   technician -> vendor mapping.
3. **DB migration** for the new fields + upsert logic.
4. **Procrastinate task:** fail-safe, env-aware, feature-flagged off by
   default.
5. **Frontend:** panels + the on-site stage.
6. **Infra:** add Playwright + Chromium to the worker Docker image,
   bump the Fly worker machine RAM.

## Infra implications

- Chromium adds ~300-400MB to the worker image, needs more RAM
  (~1GB+ machine), and slows deploys/cold starts.
- Alternative considered: replicate the SSO login as pure HTTP calls
  (no browser) to avoid Chromium. Lighter at runtime, but SSO flows
  carry CSRF tokens, redirects, and JS challenges that are brittle to
  reverse-engineer and maintain. The browser is the robust path.

## Risks (weigh heavily)

- **Terms of Service.** Automating the portal login circumvents the
  sanctioned API. It is our own account and data (defensible), but it
  can violate SC's terms and, worst case, get the account flagged or
  blocked. That same account runs the partner-API sync the *entire
  dashboard* depends on. Jeopardizing the working integration for a
  secondary feature is the scariest risk. Mitigate by using a
  non-critical login if one can be provisioned.
- **Fragility.** Headless SSO logins break on UI changes, MFA prompts,
  CAPTCHAs, or Cloudflare/bot-detection. Enterprise portals add these
  routinely.
- **Maintenance.** Standing liability for a solo, evenings-and-weekends
  dev. Silent breakage shows stale assignments and erodes trust.
- **May be moot.** The SC Workforce permissions email is already out.
  If SC grants API access (or enables SDI Mobile), this entire effort
  is throwaway and we get the data the supported way.

## Recommendation

**Wait for SC's reply to the permissions email before building.** If
they grant access, we get the data cleanly with none of the
ToS/fragility/infra cost. If they decline, build this as the documented
fallback: **isolated, feature-flagged, fail-safe, and ideally on a
non-critical login** so a flag/block cannot take down the main
integration. The token-harvest design above is the right shape.

Rough effort if we proceed: spike is half a day (the real risk gate);
full build is ~1 to 2 weeks of evening work, mostly in fragility
handling and worker infra, not happy-path code.
