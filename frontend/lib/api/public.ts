/**
 * Public-API fetcher — for endpoints that don't require auth.
 *
 * Used by the marketing storefront, which renders to anonymous
 * visitors and must not require a Supabase session. The shape
 * mirrors `apiFetch` from `server.ts` but skips the token
 * attachment.
 */

import { ApiError } from '@/lib/api/server'

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

export async function publicFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json' },
    // The storefront is read-heavy and content rarely changes —
    // tag the fetch so we can revalidate on demand from the editor's
    // save action (revalidateTag('storefront')) instead of busting
    // on every request.
    next: { tags: ['storefront'] },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // Body wasn't JSON; status text is the fallback.
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}
