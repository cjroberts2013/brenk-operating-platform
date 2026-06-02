/**
 * Single voice-of-customer quote. Centered, max-width 880px,
 * Archivo 700 blockquote. Placeholder copy for v1.
 */

import { TESTIMONIAL } from './data'

export function Testimonial() {
  return (
    <section className="bg-mist py-24 sm:py-16">
      <div className="mx-auto w-full max-w-[880px] px-5 text-center sm:px-8">
        <span
          aria-hidden
          className="block h-10 font-display text-[90px] leading-[0.1] text-signal"
        >
          “
        </span>
        <blockquote className="m-0 font-display text-[clamp(24px,2.6vw,34px)] leading-[1.28] font-bold tracking-[-0.01em] text-ink">
          {TESTIMONIAL.quote}
        </blockquote>
        <div className="mt-[26px] font-mono-brand text-[13px] tracking-[0.04em] text-slate-body uppercase">
          {TESTIMONIAL.attribution}
        </div>
      </div>
    </section>
  )
}
