/**
 * "Why Brenk" — 4 value-prop cards. White cards on light bg,
 * navy icon tiles with a white glyph, hover lifts −4px + shadow
 * upgrade. 4-col on desktop, 2-col below 1000px, 1-col below
 * 620px.
 */

import { VALUE_PROPS } from './data'
import { ValuePropIcon } from './icons'

export function ValueProps() {
  return (
    <section className="py-24">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        {/* Center-aligned section heading */}
        <div className="mx-auto max-w-[720px] text-center">
          <span className="eyebrow justify-center">
            Why facility managers choose Brenk
          </span>
          <h2 className="mt-4 mb-[14px] font-display text-[clamp(30px,3.6vw,44px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-ink">
            Less coordination. More uptime.
          </h2>
        </div>

        <div className="mt-[52px] grid grid-cols-1 gap-[22px] min-[620px]:grid-cols-2 min-[1000px]:grid-cols-4">
          {VALUE_PROPS.map((v) => (
            <div
              key={v.title}
              className="rounded-xl border border-line-brand bg-white px-6 py-7 shadow-brand-sm transition-[transform,box-shadow] duration-150 ease-out hover:-translate-y-1 hover:shadow-brand-md"
            >
              <span className="mb-[18px] grid size-[46px] place-items-center rounded-[10px] bg-navy">
                <ValuePropIcon iconKey={v.iconKey} className="size-6 text-white" />
              </span>
              <h3 className="mb-[9px] font-display text-[19px] leading-[1.2] font-extrabold tracking-[-0.02em] text-ink">
                {v.title}
              </h3>
              <p className="text-[15px] leading-[1.55] text-slate-body">{v.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
