/**
 * Attachment download proxy.
 *
 * A plain `<a href>`/`<img src>` can't attach the Supabase JWT the backend
 * requires, so this same-origin route handler (cookie-authenticated by the
 * dashboard) reads the session, calls the FastAPI download endpoint with the
 * access token, and streams the bytes straight back. FastAPI in turn resolves
 * a fresh presigned SC URL and fetches the file — the transient URL and the
 * SC token never reach the browser.
 *
 * `?download=1` forces an attachment (save) disposition; otherwise inline so
 * images can preview.
 */

import { createSupabaseServerClient } from '@/lib/supabase/server'

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; attachmentId: string }> },
): Promise<Response> {
  const { id, attachmentId } = await params

  const supabase = await createSupabaseServerClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session) {
    return new Response('Unauthorized', { status: 401 })
  }

  const download = new URL(request.url).searchParams.get('download') === '1'
  const backendUrl =
    `${API_URL}/api/v1/work-orders/${id}/attachments/${attachmentId}/download` +
    (download ? '?download=true' : '')

  const upstream = await fetch(backendUrl, {
    headers: { Authorization: `Bearer ${session.access_token}` },
    cache: 'no-store',
  })

  if (!upstream.ok || !upstream.body) {
    return new Response('Attachment unavailable', { status: upstream.status })
  }

  const headers = new Headers()
  const contentType = upstream.headers.get('content-type')
  if (contentType) headers.set('content-type', contentType)
  const disposition = upstream.headers.get('content-disposition')
  if (disposition) headers.set('content-disposition', disposition)

  return new Response(upstream.body, { status: 200, headers })
}
