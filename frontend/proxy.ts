/**
 * Auth proxy (Next.js 16 — `proxy.ts` replaces the deprecated
 * `middleware.ts` file convention; same shape, same runtime, new name).
 *
 * Runs on every non-static request. Two responsibilities:
 *   1. Refresh the Supabase session cookie if the access token is near
 *      expiry. Required for SSR — without this, server components see
 *      a stale `user` after the token would have refreshed in the
 *      browser.
 *   2. Redirect unauthenticated requests to /login (except for /login
 *      itself and the /auth/* callback routes).
 */

import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

const PUBLIC_PATH_PREFIXES = ['/login', '/auth']

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          )
          response = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  // Calling getUser() forces a token-refresh check and surfaces the
  // session to subsequent server-side reads.
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const path = request.nextUrl.pathname
  const isPublic = PUBLIC_PATH_PREFIXES.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  )

  if (!user && !isPublic) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/login'
    loginUrl.searchParams.set('next', path)
    return NextResponse.redirect(loginUrl)
  }

  // Already-signed-in users hitting /login go to the dashboard. Avoids
  // the awkward "I'm logged in but I'm staring at a sign-in form" case.
  if (user && path === '/login') {
    const homeUrl = request.nextUrl.clone()
    homeUrl.pathname = '/'
    homeUrl.search = ''
    return NextResponse.redirect(homeUrl)
  }

  return response
}

export const config = {
  matcher: [
    // Run on every request except Next.js internals + static assets.
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
