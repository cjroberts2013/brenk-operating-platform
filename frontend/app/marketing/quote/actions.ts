'use server'

/**
 * Server action for the storefront "Request a Quote" form.
 *
 * Runs on the Next server and POSTs to the backend's public quote
 * endpoint (server-to-server, so no CORS and the API URL stays off
 * the client). The backend logs the lead and emails Daryl via Resend.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

export type QuoteState = { ok: boolean; error: string | null }

export async function submitQuoteAction(
  _prev: QuoteState,
  formData: FormData,
): Promise<QuoteState> {
  const payload = {
    name: String(formData.get('name') ?? '').trim(),
    email: String(formData.get('email') ?? '').trim(),
    phone: String(formData.get('phone') ?? '').trim() || null,
    message: String(formData.get('message') ?? '').trim(),
    // Honeypot — real users leave this hidden field empty.
    website: String(formData.get('website') ?? ''),
  }

  if (!payload.name || !payload.email || !payload.message) {
    return { ok: false, error: 'Please add your name, email, and a short message.' }
  }

  try {
    const res = await fetch(`${API_URL}/api/v1/storefront/quote`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      let detail = 'Something went wrong sending your request. Please call us instead.'
      if (res.status === 422) {
        detail = 'Please double-check your email address and try again.'
      }
      return { ok: false, error: detail }
    }
    return { ok: true, error: null }
  } catch {
    return {
      ok: false,
      error: 'We couldn’t reach the server. Please call us at (512) 369-2719.',
    }
  }
}
