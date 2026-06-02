/**
 * 7 grouped service categories on a mist background. Scannable
 * directory — deliberately no per-service click-through (a
 * stakeholder decision documented in the design handoff).
 *
 * Each group: 30×30 icon chip (blue glyph on pale blue) + H3 +
 * 2px navy bottom border + bulleted item list. 4-col on desktop,
 * 2-col below 1000px, 1-col below 620px.
 *
 * Footer note + "Talk to our team" link catches anyone whose
 * trade they don't see represented.
 */

import { SERVICE_GROUPS } from './data'
import { ArrowRightIcon, ServiceGroupIcon } from './icons'

export function ServicesDirectory() {
  return (
    <section id="services" className="bg-mist py-24">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-[720px]">
            <span className="eyebrow">What we do</span>
            <h2 className="mt-4 mb-[14px] font-display text-[clamp(30px,3.6vw,44px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-ink">
              Everything your facility needs, under one roof
            </h2>
            <p className="text-[19px] leading-[1.6] text-slate-body">
              From day-to-day maintenance to ground-up construction, a single
              source of accountability across every trade.
            </p>
          </div>
          <a
            href="#"
            className="inline-flex items-center justify-center gap-[9px] rounded-md border-[1.5px] border-line-brand bg-transparent px-6 py-[15px] font-sans text-[15.5px] leading-none font-semibold whitespace-nowrap text-ink transition-colors hover:border-slate-body active:translate-y-px"
          >
            View all services
          </a>
        </div>

        <div className="mt-[54px] grid grid-cols-1 gap-x-10 gap-y-9 min-[620px]:grid-cols-2 min-[1000px]:grid-cols-4">
          {SERVICE_GROUPS.map((g) => (
            <div key={g.slug}>
              <div className="mb-4 flex items-center gap-[11px] border-b-2 border-navy pb-[14px]">
                <span className="grid size-[30px] place-items-center rounded-md bg-[#eaf1fb] text-signal">
                  <ServiceGroupIcon slug={g.slug} />
                </span>
                <h3 className="font-display text-[17px] leading-[1.2] font-bold tracking-[-0.01em] text-ink">
                  {g.title}
                </h3>
              </div>
              <ul className="m-0 flex list-none flex-col gap-[11px] p-0">
                {g.items.map((item) => (
                  <li
                    key={item}
                    className="relative pl-[18px] text-[15.5px] text-slate-body before:absolute before:top-[9px] before:left-0 before:block before:size-[7px] before:rounded-sm before:bg-signal before:content-['']"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-[46px] flex flex-wrap items-center justify-between gap-5 border-t border-line-brand pt-[26px] text-[16px] text-slate-body">
          <span>
            Don&apos;t see it listed? If it&apos;s part of your building, we
            maintain it.
          </span>
          <a
            href="/quote"
            className="group inline-flex items-center gap-[7px] font-semibold text-signal"
          >
            Talk to our team
            <ArrowRightIcon className="size-[18px] transition-transform group-hover:translate-x-[3px]" />
          </a>
        </div>
      </div>
    </section>
  )
}
