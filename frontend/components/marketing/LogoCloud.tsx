/**
 * Social-proof logo strip. 6 placeholder boxes for v1; swap for
 * real grayscale client logos when Daryl provides them. Replace
 * with real <Image> elements at that point.
 */

import { CLIENT_LOGOS } from './data'

export function LogoCloud() {
  return (
    <section className="py-[72px]">
      <div className="mx-auto w-full max-w-[1200px] px-5 text-center sm:px-8">
        <div className="font-mono-brand text-[12.5px] tracking-[0.12em] text-slate-soft uppercase">
          Trusted by facility & property teams across the region
        </div>
        <div className="mt-[30px] grid grid-cols-3 items-center gap-[18px] min-[620px]:grid-cols-6">
          {CLIENT_LOGOS.map((label, i) => (
            <div
              key={i}
              className="grid h-[44px] place-items-center rounded-md border border-dashed border-line-brand bg-mist font-mono-brand text-[10px] tracking-[0.08em] text-slate-soft"
            >
              {label}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
