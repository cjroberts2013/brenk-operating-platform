/**
 * Final-conversion strip just above the footer. Navy background,
 * H2 + sub-line on the left, two CTAs on the right (a white
 * solid + a ghost outline). Wraps to stacked on narrow widths.
 */

export function CtaBand() {
  return (
    <section id="quote" className="bg-navy text-white">
      <div className="mx-auto flex w-full max-w-[1200px] flex-wrap items-center justify-between gap-[30px] px-5 py-14 sm:px-8">
        <div>
          <h2 className="font-display text-[clamp(26px,2.8vw,38px)] leading-[1.06] font-extrabold tracking-[-0.02em] text-white">
            Need a bid or an emergency repair?
          </h2>
          <p className="mt-[10px] font-mono-brand text-[13.5px] tracking-[0.03em] text-[#9fb1c4]">
            Free quotes · 24/7 emergency response · One point of contact
          </p>
        </div>
        <div className="flex flex-wrap gap-[14px]">
          <a
            href="/quote"
            className="inline-flex items-center justify-center gap-[9px] rounded-md bg-white px-[30px] py-[17px] font-sans text-[16.5px] leading-none font-semibold whitespace-nowrap text-navy transition-colors hover:bg-[#eaf1fb] active:translate-y-px"
          >
            Request a Quote
          </a>
          <a
            href="tel:5123692719"
            className="inline-flex items-center justify-center gap-[9px] rounded-md border-[1.5px] border-white/40 px-[30px] py-[17px] font-sans text-[16.5px] leading-none font-semibold whitespace-nowrap text-white transition-colors hover:border-white active:translate-y-px"
          >
            Call the 24/7 line
          </a>
        </div>
      </div>
    </section>
  )
}
