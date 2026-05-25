/**
 * Auth proxy (Next.js 16 — `proxy.ts` replaces the deprecated
 * `middleware.ts` file convention; same shape, same runtime, new name).
 *
 * Three responsibilities:
 *   1. Refresh the Supabase session cookie if the access token is near
 *      expiry. Required for SSR — without this, server components see
 *      a stale `user` after the token would have refreshed in the
 *      browser.
 *   2. Redirect unauthenticated requests to /login (except for /login,
 *      /auth/*, /marketing/*, and bare-domain requests — see below).
 *   3. Rewrite bare-domain requests (brenkfacilityservices.com) to the
 *      /marketing route group. The dashboard lives at
 *      app.brenkfacilityservices.com; the bare domain serves the
 *      public marketing site sourced from the same Next.js project.
 */

import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

/** Paths that anyone can hit without a Supabase session. */
const PUBLIC_PATH_PREFIXES = ['/login', '/auth', '/marketing']

/** Exact paths (not prefixes) that anyone can hit. Crawler files
 *  belong at canonical paths on every host. */
const PUBLIC_PATHS = new Set(['/robots.txt', '/sitemap.xml', '/favicon.ico'])

/** True when the request host should serve the public marketing
 *  storefront instead of the dashboard. The dashboard lives at
 *  `app.<domain>`; everything else (bare apex, www, etc.) is the
 *  storefront.
 *
 *  In local dev (`localhost` / `127.0.0.1`) we serve the dashboard
 *  so the editor + sign-in flow keep working. Preview the storefront
 *  at `localhost:3000/marketing` while dev'ing.
 */
function isStorefrontHost(host: string): boolean {
  const justHost = host.split(':')[0]
  if (justHost === 'localhost' || justHost === '127.0.0.1') return false
  if (justHost.startsWith('app.')) return false
  return true
}

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname
  const host = request.headers.get('host') ?? ''

  // 1. Bare-domain rewrite. If we're on a storefront host and the
  //    path doesn't already start with /marketing, /api, /_next,
  //    or one of the well-known crawler/static files, rewrite it
  //    under /marketing so Next serves the public pages.
  //
  //    Crawler files (robots.txt, sitemap.xml, favicon.ico) MUST be
  //    served at their canonical paths — search engines look there
  //    by convention and a rewrite would 404 the lookups.
  if (
    isStorefrontHost(host) &&
    !path.startsWith('/marketing') &&
    !path.startsWith('/api') &&
    !path.startsWith('/_next') &&
    path !== '/robots.txt' &&
    path !== '/sitemap.xml' &&
    path !== '/favicon.ico'
  ) {
    const rewriteUrl = request.nextUrl.clone()
    rewriteUrl.pathname = `/marketing${path === '/' ? '' : path}`
    return NextResponse.rewrite(rewriteUrl)
  }

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

  const isPublic =
    PUBLIC_PATHS.has(path) ||
    PUBLIC_PATH_PREFIXES.some(
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
