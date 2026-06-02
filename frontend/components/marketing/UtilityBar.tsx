/**
 * Persistent micro-trust + emergency contact strip.
 *
 * Full-width navy-deep band, mono 12.5px. Left side hides below
 * 620px to keep the 24/7 emergency phone visible at all sizes —
 * that's the priority on a small viewport.
 */

import {
  EMERGENCY_PHONE,
  EMERGENCY_PHONE_HREF,
  TAGLINE_SINCE,
  TAGLINE_TRUST,
} from './data'

export function UtilityBar() {
  return (
    <div className="bg-navy-deep font-mono-brand text-[12.5px] tracking-[0.02em] text-[#c7d3e0]">
      <div className="mx-auto flex min-h-[38px] w-full max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        <div className="hidden gap-[22px] max-[620px]:hidden min-[620px]:flex">
          <span>{TAGLINE_SINCE}</span>
          <a href="#" className="hover:text-white">
            {TAGLINE_TRUST}
          </a>
        </div>
        <div className="flex items-center gap-[22px]">
          <a href="#" className="hover:text-white">
            Service Areas
          </a>
          <span className="inline-flex items-center gap-2 text-white">
            <span className="emerg-dot" aria-hidden />
            <b className="font-semibold text-ember">24/7 Emergency</b>
            <a href={EMERGENCY_PHONE_HREF} className="hover:text-white">
              {EMERGENCY_PHONE}
            </a>
          </span>
        </div>
      </div>
    </div>
  )
}
