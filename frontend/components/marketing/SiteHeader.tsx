/**
 * Sticky main navigation. Translucent blur background, 76px
 * min-height, brand mark + wordmark on the left, desktop links
 * in the middle (hidden below 1000px), Client Login + Request a
 * Quote on the right. Animated underline on link hover.
 *
 * Below 1000px the desktop links collapse and the `MobileMenu`
 * hamburger appears in their place.
 *
 * `relative` on the wrapper so the mobile drawer can position
 * absolutely against it.
 */

import { BrandMark } from './brand'
import { MobileMenu } from './MobileMenu'
import { NAV_LINKS } from './data'

export function SiteHeader({ logoUrl }: { logoUrl: string | null }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line-brand bg-white/90 backdrop-blur-[10px]">
      <div className="relative mx-auto flex w-full min-h-[76px] max-w-[1200px] items-center justify-between gap-6 px-5 sm:px-8">
        <BrandMark logoUrl={logoUrl} />

        <nav className="hidden gap-[30px] min-[1000px]:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="nav-link text-[15.5px] font-medium text-ink"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-[18px]">
          <a
            href="/quote"
            className="hidden items-center justify-center gap-[9px] rounded-md bg-signal px-6 py-[15px] font-sans text-[15.5px] leading-none font-semibold whitespace-nowrap text-white shadow-[0_8px_20px_-10px_rgba(29,95,184,0.7)] transition-colors hover:bg-signal-ink active:translate-y-px min-[1000px]:inline-flex"
          >
            Request a Quote
          </a>
          <MobileMenu />
        </div>
      </div>
    </header>
  )
}
