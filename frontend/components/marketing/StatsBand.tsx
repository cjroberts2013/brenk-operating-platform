/**
 * 4-col stats grid on a navy band + credentials strip below
 * separated by a thin top border. Numbers in Archivo 800,
 * captions in IBM Plex Mono uppercase. Credential checks use
 * the ember accent — one of two places it appears on the page
 * (the other is the 24/7 emergency dot).
 *
 * Margin-top: 78px overlaps the hero rhythm, per the design.
 */

import { CREDENTIALS, STATS } from './data'

export function StatsBand() {
  return (
    <section className="mt-[78px] bg-navy py-16 text-white">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="grid grid-cols-1 gap-x-3 gap-y-[26px] min-[620px]:grid-cols-3 min-[620px]:gap-y-3">
          {STATS.map((s, i) => (
            <div
              key={s.label}
              className={
                'relative px-2 py-[6px] text-left ' +
                (i > 0
                  ? "min-[620px]:before:absolute min-[620px]:before:-left-[6px] min-[620px]:before:top-1/2 min-[620px]:before:h-[54px] min-[620px]:before:w-px min-[620px]:before:-translate-y-1/2 min-[620px]:before:bg-white/15 min-[620px]:before:content-['']"
                  : '')
              }
            >
              <div className="font-display text-[clamp(34px,3.4vw,46px)] leading-none font-extrabold text-white">
                {s.num}
              </div>
              <div className="mt-[10px] font-mono-brand text-[12px] tracking-[0.04em] text-[#9fb1c4] uppercase">
                {s.label}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-9 flex flex-wrap gap-x-[30px] gap-y-3 border-t border-white/15 pt-6">
          {CREDENTIALS.map((c) => (
            <span
              key={c}
              className="inline-flex items-center gap-[9px] font-mono-brand text-[13px] tracking-[0.03em] text-[#cdd8e4]"
            >
              <span aria-hidden className="font-bold text-ember">
                ✓
              </span>
              {c}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
