/**
 * Brand mark + wordmark + kicker, reused by the nav header and
 * the footer. Two variants:
 *   - `default` — navy tile, navy wordmark (against light bg)
 *   - `footer`  — white tile, white wordmark (against navy bg)
 *
 * When Daryl provides a real logo (Phase B), this renders the
 * uploaded image instead of the typographic stand-in.
 */

import Image from 'next/image'

export function BrandMark({
  variant = 'default',
  logoUrl,
}: {
  variant?: 'default' | 'footer'
  logoUrl?: string | null
}) {
  const isFooter = variant === 'footer'

  return (
    <a href="/" className="flex items-center gap-3">
      {logoUrl ? (
        <Image
          src={logoUrl}
          alt="Brenk Facility Services"
          width={38}
          height={38}
          unoptimized
          className="size-[38px] rounded-[7px] object-contain"
        />
      ) : (
        <span
          className={
            'grid size-[38px] place-items-center rounded-[7px] font-display text-[20px] leading-none font-extrabold tracking-[-1px] ' +
            (isFooter ? 'bg-white text-navy' : 'bg-navy text-white')
          }
        >
          B
        </span>
      )}
      <span
        className={
          'flex flex-col font-display text-[21px] leading-none font-extrabold tracking-[0.02em] ' +
          (isFooter ? 'text-white' : 'text-navy')
        }
      >
        BRENK
        <span
          className={
            'mt-[3px] font-mono-brand text-[10px] font-medium tracking-[0.28em] ' +
            (isFooter ? 'text-[#7e8fa1]' : 'text-slate-body')
          }
        >
          FACILITY SERVICES
        </span>
      </span>
    </a>
  )
}
