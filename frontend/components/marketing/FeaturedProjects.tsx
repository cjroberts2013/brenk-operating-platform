/**
 * 3-card case-study row. Photo placeholder on top, body with tag
 * pill + title + 1-line description + metric footer. Hover lifts
 * −4px + shadow upgrade.
 *
 * This is the surface most likely to need DB-backed editing in
 * Phase B — projects come and go as Brenk completes work. Until
 * then, the `PROJECTS` array in data.ts is source of truth.
 */

import { PROJECTS } from './data'

export function FeaturedProjects() {
  return (
    <section id="projects" className="py-24">
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="max-w-[720px]">
          <span className="eyebrow">Recent work</span>
          <h2 className="mt-4 mb-[14px] font-display text-[clamp(30px,3.6vw,44px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-ink">
            Proof in the field
          </h2>
        </div>

        <div className="mt-[52px] grid grid-cols-1 gap-6 min-[1000px]:grid-cols-3">
          {PROJECTS.map((p) => (
            <article
              key={p.title}
              className="overflow-hidden rounded-xl border border-line-brand bg-white shadow-brand-sm transition-[transform,box-shadow] duration-150 ease-out hover:-translate-y-1 hover:shadow-brand-md"
            >
              <div className="photo-ph aspect-[16/10] rounded-none border-0 border-b border-line-brand">
                <span className="photo-cap">{p.photoCaption}</span>
              </div>
              <div className="px-[22px] pt-[22px] pb-6">
                <span className="inline-block rounded-full bg-[#eaf1fb] px-[10px] py-[5px] font-mono-brand text-[11px] tracking-[0.08em] text-signal uppercase">
                  {p.tag}
                </span>
                <h3 className="my-[14px] font-display text-[20px] leading-[1.2] font-extrabold tracking-[-0.02em] text-ink">
                  {p.title}
                </h3>
                <p className="text-[14.5px] leading-[1.55] text-slate-body">
                  {p.description}
                </p>
                <div className="mt-4 border-t border-line-brand pt-4 font-mono-brand text-[13px] text-ink">
                  {p.metrics.map((m, i) => (
                    <span key={m.label}>
                      <b className="font-semibold text-signal">{m.value}</b>{' '}
                      {m.label}
                      {i < p.metrics.length - 1 ? ' · ' : ''}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
