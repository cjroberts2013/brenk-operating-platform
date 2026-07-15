/**
 * Locations Excel export proxy.
 *
 * A plain `<a href>` can't attach the Supabase JWT the backend requires, so
 * this same-origin route handler (cookie-authenticated by the dashboard)
 * reads the session, calls the FastAPI export endpoint with the access
 * token, and streams the .xlsx straight back. The current search/rating
 * filters are forwarded so the download matches what the user is viewing.
 *
 * Static `export/route.ts` takes precedence over the dynamic
 * `[id]/page.tsx`, so `/locations/export` resolves here, not to a location
 * detail.
 */

import { createSupabaseServerClient } from '@/lib/supabase/server'

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

export async function GET(request: Request): Promise<Response> {
  const supabase = await createSupabaseServerClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session) {
    return new Response('Unauthorized', { status: 401 })
  }

  const incoming = new URL(request.url).searchParams
  const forwarded = new URLSearchParams()
  const q = incoming.get('q')
  if (q) forwarded.set('q', q)
  const rating = incoming.get('rating')
  if (rating) forwarded.set('rating', rating)

  const backendUrl =
    `${API_URL}/api/v1/locations/export.xlsx` +
    (forwarded.size ? `?${forwarded}` : '')

  const upstream = await fetch(backendUrl, {
    headers: { Authorization: `Bearer ${session.access_token}` },
    cache: 'no-store',
  })

  if (!upstream.ok || !upstream.body) {
    return new Response('Export unavailable', { status: upstream.status })
  }

  const headers = new Headers()
  const contentType = upstream.headers.get('content-type')
  if (contentType) headers.set('content-type', contentType)
  const disposition = upstream.headers.get('content-disposition')
  if (disposition) headers.set('content-disposition', disposition)

  return new Response(upstream.body, { status: 200, headers })
}
