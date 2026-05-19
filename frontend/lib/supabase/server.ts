/**
 * Server-side Supabase client (cookie-aware).
 *
 * Use this from Server Components, Server Actions, and Route Handlers.
 * The middleware uses its own variant (see `middleware.ts`) because
 * Next.js NextResponse exposes a different cookie API.
 *
 * Why `await cookies()`: in Next.js 15+, `cookies()` is async and must
 * be awaited even though it returns the cookie store synchronously
 * once resolved.
 */

import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createSupabaseServerClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options)
            })
          } catch {
            // Server Components can't set cookies. Middleware handles
            // session refresh, so silently ignore here — this matches
            // the Supabase docs' recommended pattern.
          }
        },
      },
    },
  )
}
