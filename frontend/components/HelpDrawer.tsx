'use client'

import { Dialog, DialogBackdrop, DialogPanel } from '@headlessui/react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { QuestionMarkCircleIcon } from '@heroicons/react/20/solid'

import { helpForPath } from '@/lib/help-content'

/**
 * Contextual help slide-over. Opened from the "?" in the top bar; shows the
 * help entry for the page you're on (lib/help-content.ts). Pure UI — no data
 * fetching. Same right-side Dialog pattern as the mobile sidebar in AppShell.
 */
export function HelpDrawer({
  open,
  onClose,
  pathname,
}: {
  open: boolean
  onClose: () => void
  pathname: string
}) {
  const entry = helpForPath(pathname)

  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-gray-900/40 transition-opacity duration-200 ease-linear data-closed:opacity-0"
      />
      <div className="fixed inset-0 flex justify-end">
        <DialogPanel
          transition
          className="flex w-full max-w-sm transform flex-col overflow-y-auto bg-white shadow-xl transition duration-200 ease-in-out data-closed:translate-x-full dark:bg-gray-900 dark:ring-1 dark:ring-white/10"
        >
          <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-white/10">
            <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900 dark:text-white">
              <QuestionMarkCircleIcon className="size-5 text-indigo-500" aria-hidden="true" />
              Help · {entry.title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close help"
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-white/5 dark:hover:text-gray-200"
            >
              <XMarkIcon className="size-5" />
            </button>
          </div>

          <div className="space-y-5 px-5 py-5">
            <p className="text-sm text-gray-600 dark:text-gray-300">{entry.intro}</p>

            {entry.sections.map((section, i) => (
              <div key={i} className="space-y-2">
                {section.heading ? (
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                    {section.heading}
                  </h3>
                ) : null}
                <ul className="space-y-2">
                  {section.items.map((item, j) => (
                    <li
                      key={j}
                      className="flex gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-2 size-1.5 shrink-0 rounded-full bg-indigo-400"
                      />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <p className="mt-auto border-t border-gray-200 px-5 py-4 text-xs text-gray-500 dark:border-white/10 dark:text-gray-400">
            Stuck on something? Reach out to Charles.
          </p>
        </DialogPanel>
      </div>
    </Dialog>
  )
}
