import { ABOUT } from '@/components/marketing/data'
import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { getStorefrontPublic } from '@/lib/api/storefront'

export const metadata = {
  title: 'About · Brenk Facility Services',
  description:
    'Brenk Facility Services is a family-owned facility services company in Austin, TX, serving over 180 facilities since 2007.',
}

/**
 * Public "About" page at the bare domain (`/about`, rewritten to
 * `/marketing/about` by proxy.ts). Shares the storefront chrome.
 *
 * Copy is hardcoded in `components/marketing/data.ts` (ABOUT) for now.
 * The photo uses the operator-editable `about_image_url` from the
 * Storefront content when set, with a placeholder until one is added.
 */
export default async function AboutPage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <main className="mx-auto w-full max-w-[1200px] px-5 py-16 sm:px-8 sm:py-20">
        <h1 className="font-display text-[clamp(34px,5vw,52px)] leading-[1.04] font-extrabold tracking-[-0.02em] text-ink">
          About us
        </h1>

        <div className="mt-10 grid grid-cols-1 items-start gap-10 lg:mt-14 lg:grid-cols-2 lg:gap-16">
          {/* Photo. Uses the operator-editable about_image_url when set,
              otherwise the bundled family photo in /public. */}
          <div className="overflow-hidden rounded-2xl bg-mist ring-1 ring-line-brand">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={content.about_image_url || '/images/family.jpg'}
              alt="The Brenk family"
              className="h-full w-full object-cover"
            />
          </div>

          {/* Copy */}
          <div>
            <p className="font-mono-brand text-[12.5px] tracking-[0.06em] text-signal uppercase">
              {ABOUT.eyebrow}
            </p>
            <h2 className="mt-3 font-display text-[clamp(26px,3.2vw,40px)] leading-[1.08] font-extrabold tracking-[-0.02em] text-ink">
              {ABOUT.heading}
            </h2>
            <div className="mt-6 space-y-5">
              {ABOUT.paragraphs.map((para, i) => (
                <p key={i} className="text-[16.5px] leading-relaxed text-slate-body">
                  {para}
                </p>
              ))}
            </div>

            <a
              href="/quote"
              className="mt-9 inline-flex items-center justify-center rounded-md bg-signal px-7 py-4 font-sans text-[16px] font-semibold text-white transition-colors hover:bg-signal-ink active:translate-y-px"
            >
              Request a Quote
            </a>
          </div>
        </div>
      </main>

      <SiteFooter
        tagline={content.footer_tagline}
        copyright={content.footer_copyright}
      />
    </>
  )
}
