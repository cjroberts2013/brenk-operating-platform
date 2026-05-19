/**
 * Browser-side Supabase client.
 *
 * Use this from Client Components only. For Server Components / Route
 * Handlers / Server Actions / Middleware, use the `server.ts` factory
 * which is cookie-aware.
 */

import { createBrowserClient } from '@supabase/ssr'

export function createSupabaseBrowserClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  )
}
