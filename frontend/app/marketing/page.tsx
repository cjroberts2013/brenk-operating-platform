import { Certifications } from '@/components/marketing/Certifications'
import { CtaBand } from '@/components/marketing/CtaBand'
import { FeaturedProjects } from '@/components/marketing/FeaturedProjects'
import { Hero } from '@/components/marketing/Hero'
import { LogoCloud } from '@/components/marketing/LogoCloud'
import { ServicesDirectory } from '@/components/marketing/ServicesDirectory'
import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { StatsBand } from '@/components/marketing/StatsBand'
import { Testimonial } from '@/components/marketing/Testimonial'
import { ValueProps } from '@/components/marketing/ValueProps'
import { getStorefrontPublic } from '@/lib/api/storefront'

/** Validate an operator-supplied href before rendering.
 *
 *  Allow:
 *   - empty / null (caller falls back to a safe default)
 *   - anchors (#contact, #quote)
 *   - http: / https: (absolute)
 *   - mailto: / tel:
 *   - relative paths that START WITH / (e.g. '/services') so the
 *     anchor stays on the bare domain
 *
 *  Block everything else — most importantly `javascript:`,
 *  `data:`, vbscript:, etc. — which would otherwise be a stored-
 *  XSS vector if a malicious editor user planted one.
 *
 *  Defense in depth — the editor has authenticated access only,
 *  but trusting operator input on render means we don't have to
 *  audit every code path that writes the field. */
function safeHref(raw: string | null, fallback = '/quote'): string {
  if (!raw) return fallback
  const trimmed = raw.trim()
  if (!trimmed) return fallback
  if (trimmed.startsWith('#')) return trimmed
  if (trimmed.startsWith('/')) return trimmed
  if (trimmed.includes(':')) {
    const lower = trimmed.toLowerCase()
    const allowed = ['http://', 'https://', 'mailto:', 'tel:']
    if (!allowed.some((p) => lower.startsWith(p))) {
      return fallback
    }
  }
  return trimmed
}

/**
 * Public marketing homepage at the bare domain.
 *
 * `proxy.ts` rewrites `brenkfacilityservices.com/*` to
 * `/marketing/*`, so this page renders for visitors hitting `/`
 * on the storefront host. The dashboard at
 * `app.brenkfacilityservices.com` never reaches this code.
 *
 * Section composition follows the 2026-05-28 hi-fi design
 * handoff (`docs/design_handoff_brenk_homepage/`). Most copy is
 * hardcoded in `components/marketing/data.ts`; the operator-
 * editable fields (hero, footer tagline, logo URL) come from
 * the Storefront API.
 */
export default async function StorefrontPage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <Hero
        title={content.hero_title}
        subtitle={content.hero_subtitle}
        ctaText={content.hero_cta_text}
        ctaHref={safeHref(content.hero_cta_link, '/quote')}
      />

      <StatsBand />
      <LogoCloud />
      <ServicesDirectory />
      <ValueProps />
      <Certifications />
      <FeaturedProjects />
      <Testimonial />
      <CtaBand />

      <SiteFooter
        tagline={content.footer_tagline}
        copyright={content.footer_copyright}
      />
    </>
  )
}
