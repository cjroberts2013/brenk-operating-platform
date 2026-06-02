/**
 * Procurement-facing trust panel — 4 credential cards on a navy
 * band. Translucent white fill + bordered badge tile + white
 * glyph + mono caption.
 */

import { CERTIFICATIONS } from './data'
import { CertificationIcon } from './icons'

export function Certifications() {
  return (
    <section id="certs" className="bg-navy py-24 text-white">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="max-w-[720px]">
          <span className="eyebrow eyebrow-on-navy">Certifications & safety</span>
          <h2 className="mt-4 mb-[14px] font-display text-[clamp(30px,3.6vw,44px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-white">
            Credentials you can hand straight to procurement
          </h2>
          <p className="text-[19px] leading-[1.6] text-[#b9c6d6]">
            Documentation on request: insurance certificates, safety records,
            and licensing for every jurisdiction we serve.
          </p>
        </div>

        <div className="mt-[50px] grid grid-cols-1 gap-[18px] min-[620px]:grid-cols-2 min-[1000px]:grid-cols-4">
          {CERTIFICATIONS.map((c) => (
            <div
              key={c.title}
              className="rounded-xl border border-white/15 bg-white/5 px-[22px] py-[26px]"
            >
              <span className="mb-[18px] grid size-[52px] place-items-center rounded-[10px] border-[1.5px] border-white/25 text-white">
                <CertificationIcon iconKey={c.iconKey} className="size-6 text-white" />
              </span>
              <h3 className="mb-[6px] font-display text-[18px] leading-[1.2] font-extrabold tracking-[-0.02em] text-white">
                {c.title}
              </h3>
              <p className="font-mono-brand text-[12px] tracking-[0.02em] text-[#9fb1c4]">
                {c.caption}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
