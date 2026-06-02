import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { getStorefrontPublic } from '@/lib/api/storefront'

import { QuoteForm } from './QuoteForm'

export const metadata = {
  title: 'Request a Quote · Brenk Facility Services',
  description:
    'Tell us about your facility and the work you need. We respond fast. One point of contact, free quotes.',
}

/**
 * Public "Request a Quote" page at the bare domain (`/quote`,
 * rewritten to `/marketing/quote` by proxy.ts). Shares the
 * storefront header/footer chrome; the form posts to the backend's
 * public quote endpoint, which emails Daryl.
 */
export default async function QuotePage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <main className="mx-auto w-full max-w-[760px] px-5 py-16 sm:px-8">
        <header className="mb-8">
          <p className="font-mono-brand text-[12.5px] tracking-[0.06em] text-signal uppercase">
            Free quotes · 24/7 emergency response
          </p>
          <h1 className="mt-3 font-display text-[clamp(30px,4vw,44px)] leading-[1.05] font-extrabold tracking-[-0.02em] text-ink">
            Request a quote
          </h1>
          <p className="mt-4 max-w-[60ch] text-[16.5px] leading-relaxed text-slate-600">
            Tell us about the property and the work you need. You’ll reach Daryl
            directly. One point of contact, no call-center runaround. Prefer to
            talk now? Call{' '}
            <a href="tel:5123692719" className="font-semibold text-signal">
              (512) 369-2719
            </a>
            .
          </p>
        </header>

        <QuoteForm />
      </main>

      <SiteFooter
        tagline={content.footer_tagline}
        copyright={content.footer_copyright}
      />
    </>
  )
}
