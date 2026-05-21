/**
 * Server-side API client for the Brenk backend.
 *
 * Attaches the Supabase access token from the current session as a
 * Bearer header. Use only from Server Components, Server Actions, and
 * Route Handlers — relies on `createSupabaseServerClient` which reads
 * cookies via Next's `cookies()` API.
 *
 * On 401, surfaces a typed error the caller can catch and handle (e.g.
 * by redirecting to /login). The proxy already kicks unauthenticated
 * requests to /login before they reach a page, so a 401 here usually
 * means the session was invalidated server-side between proxy and
 * fetch — rare, but worth surfacing rather than silently rendering an
 * empty page.
 */

import { createSupabaseServerClient } from '@/lib/supabase/server'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`)
  }
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

async function getAccessToken(): Promise<string | null> {
  const supabase = await createSupabaseServerClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session?.access_token ?? null
}

/**
 * Build a query string from a record of params, skipping null/undefined.
 * Numbers and booleans are stringified; arrays are joined with commas.
 */
function toQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, Array.isArray(value) ? value.join(',') : String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

type ApiInit = {
  params?: Record<string, unknown>
  method?: string
  body?: unknown
}

async function _request(path: string, init: ApiInit): Promise<Response> {
  const token = await getAccessToken()
  if (!token) {
    // Should be impossible — the proxy would have redirected — but
    // refuse to make an unauthenticated backend call regardless.
    throw new ApiError(401, 'no Supabase session')
  }

  const url = `${API_URL}${path}${toQuery(init.params ?? {})}`
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
  }
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(url, {
    method: init.method ?? 'GET',
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    // Server Components default to caching aggressively; for live data
    // we want every render to hit the API.
    cache: 'no-store',
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body?.detail)) {
        // FastAPI validation errors arrive as an array of objects like
        // `{loc: ["query", "q"], msg: "...", type: "..."}`. Flatten into
        // a one-line readable string instead of swallowing the detail.
        detail = body.detail
          .map((e: { loc?: unknown[]; msg?: string }) => {
            const where = Array.isArray(e.loc) ? e.loc.join('.') : '?'
            return `${where}: ${e.msg ?? 'invalid'}`
          })
          .join(' · ')
      }
    } catch {
      // Body wasn't JSON; fall back to status text.
    }
    // Log on the server so we can see request URL + detail in the
    // dev console, separate from whatever the page does with the
    // thrown ApiError.
    console.error(
      `[apiFetch] ${init.method ?? 'GET'} ${url} → ${response.status}: ${detail}`,
    )
    throw new ApiError(response.status, detail)
  }

  return response
}

export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const response = await _request(path, init)
  return (await response.json()) as T
}

/** Variant for endpoints that return 204 or otherwise have no body. */
export async function apiFetchVoid(path: string, init: ApiInit = {}): Promise<void> {
  await _request(path, init)
}
