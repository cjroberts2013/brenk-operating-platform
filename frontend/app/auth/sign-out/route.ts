import { type NextRequest, NextResponse } from 'next/server'

import { createSupabaseServerClient } from '@/lib/supabase/server'

/**
 * POST /auth/sign-out
 *
 * Clears the Supabase session cookies and redirects to /login.
 * Mounted as a Route Handler (not a Server Action) so the AppShell's
 * Sign Out menu can be a plain <form action="/auth/sign-out" method="POST">.
 */
export async function POST(request: NextRequest) {
  const supabase = await createSupabaseServerClient()
  await supabase.auth.signOut()

  // Redirect with 303 so a POST converts to GET on the next hop.
  // Build the absolute URL from the incoming request so this works
  // whether we're on localhost, a preview deploy, or production.
  return NextResponse.redirect(new URL('/login', request.url), { status: 303 })
}
