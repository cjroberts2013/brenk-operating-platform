/**
 * Social-proof logo strip of real served-facility brands. Logos render
 * full-color at a uniform height, centered and wrapping. Files live in
 * frontend/public.
 */

import { CLIENT_LOGOS } from './data'

export function LogoCloud() {
  return (
    <section className="py-[72px]">
      <div className="mx-auto w-full max-w-[1200px] px-5 text-center sm:px-8">
        <div className="font-mono-brand text-[12.5px] tracking-[0.12em] text-slate-soft uppercase">
          Trusted by facility &amp; property teams across the region
        </div>
        <div className="mt-[34px] flex flex-wrap items-center justify-center gap-x-14 gap-y-8">
          {CLIENT_LOGOS.map((logo) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={logo.src}
              src={logo.src}
              alt={logo.alt}
              className="h-14 w-auto max-w-[240px] object-contain sm:h-20"
            />
          ))}
        </div>
      </div>
    </section>
  )
}
