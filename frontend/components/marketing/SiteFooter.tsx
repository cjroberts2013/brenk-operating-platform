/**
 * Footer — 4-col grid on desktop (1.6fr 1fr 1fr 1fr), 2-col below
 * 1000px. Brand column on the left, then Services / Company /
 * Get in touch link blocks.
 *
 * Brand mark inverts vs the main nav: white tile + navy "B".
 */

import { BrandMark } from './brand'
import { FOOTER_COLUMNS } from './data'

export function SiteFooter({
  tagline,
  copyright,
}: {
  tagline: string | null
  copyright: string | null
}) {
  return (
    <footer className="bg-navy-deep pt-[72px] pb-9 text-[#aebccb]">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="grid grid-cols-1 gap-10 min-[620px]:grid-cols-2 min-[1000px]:grid-cols-[1.6fr_1fr_1fr_1fr]">
          {/* Brand col */}
          <div>
            <BrandMark variant="footer" />
            {tagline ? (
              <p className="mt-[18px] max-w-[280px] text-[14.5px] leading-[1.6] text-[#8b9bac]">
                {tagline}
              </p>
            ) : null}
          </div>

          {/* Link blocks */}
          {FOOTER_COLUMNS.map((col) => (
            <div key={col.heading}>
              <h4 className="mb-[18px] font-mono-brand text-[12px] font-medium tracking-[0.12em] text-[#6f8298] uppercase">
                {col.heading}
              </h4>
              <ul className="flex list-none flex-col gap-3 p-0">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="text-[14.5px] text-[#aebccb] hover:text-white"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-wrap justify-between gap-4 border-t border-white/10 pt-[26px] font-mono-brand text-[12px] tracking-[0.03em] text-[#6f8298]">
          <span>
            {copyright ??
              '© 2026 Brenk Facility Services. Licensed · Bonded · Insured.'}
          </span>
        </div>
      </div>
    </footer>
  )
}
