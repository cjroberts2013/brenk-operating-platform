/**
 * Host-aware robots.txt.
 *
 * The same Next.js project serves two hosts:
 *   - bare domain (brenkfacilityservices.com) → public storefront
 *   - app subdomain (app.brenkfacilityservices.com) → dashboard
 *
 * We want search engines to crawl the storefront freely, but to
 * leave the dashboard alone — both because the dashboard contains
 * no public content and because an indexed "Sign in" page invites
 * brute-force noise from crawlers.
 *
 * Returns different content per host. Cache-Control is set so
 * Vercel's edge cache doesn't conflate the two.
 */

import { NextRequest } from 'next/server'

export function GET(request: NextRequest) {
  const host = (request.headers.get('host') ?? '').split(':')[0]
  const isDashboard = host.startsWith('app.')

  const body = isDashboard
    ? // Dashboard subdomain — block everything.
      ['User-agent: *', 'Disallow: /', ''].join('\n')
    : // Bare-domain storefront — allow crawl, block the API.
      // (Sitemap.xml deferred to a follow-up — would help SEO once
      // we have multi-page content worth indexing.)
      ['User-agent: *', 'Allow: /', 'Disallow: /api/', ''].join('\n')

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      // Vary on Host so the edge cache keeps separate copies for
      // bare-domain vs app.*. Without this a single cached robots.txt
      // could leak between hosts.
      Vary: 'Host',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
