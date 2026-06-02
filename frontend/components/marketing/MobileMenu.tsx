'use client'

/**
 * Hamburger + slide-down drawer for narrow viewports.
 *
 * The design prototype just hid the desktop nav below 1000px;
 * the README explicitly calls this out as a production gap that
 * needs a real mobile menu. Single client component using local
 * state — no portal needed since the drawer pushes content
 * down rather than overlaying it, which keeps the layout
 * predictable and screen-reader-friendly.
 *
 * Only renders below 1000px (`min-[1000px]:hidden`).
 */

import { useState } from 'react'
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline'

import { NAV_LINKS } from './data'

export function MobileMenu() {
  const [open, setOpen] = useState(false)

  return (
    <div className="min-[1000px]:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="brenk-mobile-menu"
        aria-label={open ? 'Close menu' : 'Open menu'}
        onClick={() => setOpen((v) => !v)}
        className="grid size-10 place-items-center rounded-md border border-line-brand bg-white text-ink hover:border-slate-body"
      >
        {open ? (
          <XMarkIcon className="size-5" />
        ) : (
          <Bars3Icon className="size-5" />
        )}
      </button>

      {open ? (
        <div
          id="brenk-mobile-menu"
          className="absolute top-full right-0 left-0 border-b border-line-brand bg-white shadow-brand-md"
        >
          <ul className="mx-auto flex w-full max-w-[1200px] flex-col gap-1 px-5 py-4 sm:px-8">
            {NAV_LINKS.map((l) => (
              <li key={l.label}>
                <a
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="block rounded-md px-3 py-3 text-[16px] font-medium text-ink hover:bg-mist hover:text-signal"
                >
                  {l.label}
                </a>
              </li>
            ))}
            <li className="mt-2 border-t border-line-brand pt-3">
              <a
                href="/quote"
                onClick={() => setOpen(false)}
                className="block rounded-md bg-signal px-3 py-3 text-center font-sans text-[15.5px] font-semibold text-white hover:bg-signal-ink"
              >
                Request a Quote
              </a>
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  )
}
