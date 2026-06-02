/**
 * Above-the-fold hero — 2-col grid (1.05fr / 0.95fr), 56px gap.
 * Left column: eyebrow + H1 + lede + CTA row + assurance items.
 * Right column: photo placeholder + overlapping stat card.
 *
 * Collapses to a single column below 1000px; the overlapping
 * stat card stays anchored to the bottom-left of the image but
 * scoots in from -28px to +16px on smaller widths so it doesn't
 * hang off the viewport edge.
 *
 * The four content fields (title / subtitle / CTA text + link)
 * come from the Storefront content singleton; everything else
 * is hardcoded for v1.
 */

import { ArrowRightIcon } from './icons'

export function Hero({
  title,
  subtitle,
  ctaText,
  ctaHref,
}: {
  title: string | null
  subtitle: string | null
  ctaText: string | null
  ctaHref: string
}) {
  return (
    <section className="pt-[78px] pb-0">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="grid grid-cols-1 items-center gap-10 min-[1000px]:grid-cols-[1.05fr_0.95fr] min-[1000px]:gap-14">
          {/* Copy column */}
          <div>
            <span className="eyebrow">Commercial Facility Maintenance</span>
            <h1 className="mt-[18px] font-display text-[clamp(38px,5.2vw,62px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-ink">
              {title ?? 'One partner for every system in your building.'}
            </h1>
            <p className="mt-[22px] max-w-[520px] text-[19px] leading-[1.6] text-slate-body">
              {subtitle ??
                'HVAC, electrical, plumbing, grounds, and full build-outs, managed by one accountable team that keeps your facilities running and your tenants happy.'}
            </p>

            <div className="mt-[34px] flex flex-wrap gap-[14px]">
              <a
                href={ctaHref}
                className="group inline-flex items-center justify-center gap-[9px] rounded-md bg-signal px-[30px] py-[17px] font-sans text-[16.5px] leading-none font-semibold whitespace-nowrap text-white shadow-[0_8px_20px_-10px_rgba(29,95,184,0.7)] transition-colors hover:bg-signal-ink active:translate-y-px"
              >
                {ctaText ?? 'Request a Quote'}
                <ArrowRightIcon className="size-[18px] transition-transform group-hover:translate-x-[3px]" />
              </a>
              <a
                href="#services"
                className="inline-flex items-center justify-center gap-[9px] rounded-md border-[1.5px] border-line-brand bg-transparent px-[30px] py-[17px] font-sans text-[16.5px] leading-none font-semibold whitespace-nowrap text-ink transition-colors hover:border-slate-body active:translate-y-px"
              >
                Explore Services
              </a>
            </div>

            <div className="mt-[28px] flex flex-wrap gap-[18px] font-mono-brand text-[12.5px] tracking-[0.04em] text-slate-body uppercase">
              {[
                'One vendor, every trade',
                '< 2 hr emergency response',
                'Single point of contact',
              ].map((t) => (
                <span key={t} className="inline-flex items-center gap-2">
                  <span aria-hidden className="block size-[6px] rounded-full bg-signal" />
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* Media column — just the photo. The original design
           * overlaid a "<2 hr average emergency response time" stat
           * card here; Charles removed it 2026-05-28 so the hero
           * image reads cleaner. The assurance row below the CTAs
           * still surfaces the same "< 2 hr emergency response"
           * line, so the message isn't lost. */}
          <div className="relative">
            <div className="photo-ph aspect-[4/3.4]">
              <span className="photo-cap">Crew servicing rooftop HVAC unit</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
