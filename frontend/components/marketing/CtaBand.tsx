/**
 * Final-conversion strip just above the footer. Navy background,
 * H2 + sub-line on the left, a single "Request a Quote" CTA on the
 * right. Wraps to stacked on narrow widths.
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
            Free quotes · One point of contact
          </p>
        </div>
        <div className="flex flex-wrap gap-[14px]">
          <a
            href="/quote"
            className="inline-flex items-center justify-center gap-[9px] rounded-md bg-white px-[30px] py-[17px] font-sans text-[16.5px] leading-none font-semibold whitespace-nowrap text-navy transition-colors hover:bg-[#eaf1fb] active:translate-y-px"
          >
            Request a Quote
          </a>
        </div>
      </div>
    </section>
  )
}
