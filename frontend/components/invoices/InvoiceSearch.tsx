'use client'

import { useEffect, useRef, useState, useTransition } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/20/solid'

/**
 * Search box for the (invoice-centric) Invoices list. Debounced; writes
 * `?inv_q=` on the current URL and resets `?inv_page=`, preserving every
 * other param (the status tab, the worklist tab below). Self-contained —
 * mirrors the top-bar ContextualSearch contract but scoped to this
 * section's own params so the two lists on the page don't collide.
 */
const DEBOUNCE_MS = 200

export function InvoiceSearch() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [, startTransition] = useTransition()

  const [value, setValue] = useState<string>(() => searchParams.get('inv_q') ?? '')
  const lastPushedRef = useRef<string>(searchParams.get('inv_q') ?? '')

  // Resync from external URL changes (back/forward, paste-link) without
  // clobbering characters typed since our own last push.
  useEffect(() => {
    const urlValue = searchParams.get('inv_q') ?? ''
    if (urlValue === lastPushedRef.current) return
    lastPushedRef.current = urlValue
    setValue(urlValue)
  }, [searchParams])

  useEffect(() => {
    const trimmed = value.trim()
    if (trimmed === lastPushedRef.current) return
    const handle = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString())
      if (trimmed) next.set('inv_q', trimmed)
      else next.delete('inv_q')
      next.delete('inv_page') // row count shrinks; page N is likely stale
      lastPushedRef.current = trimmed
      const qs = next.toString()
      startTransition(() => {
        router.replace(qs ? `/invoices?${qs}` : '/invoices', { scroll: false })
      })
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(handle)
  }, [value, router, searchParams])

  return (
    <div className="relative w-full sm:max-w-xs">
      <MagnifyingGlassIcon
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-gray-400"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search invoice #, WO #, location…"
        aria-label="Search invoices"
        autoComplete="off"
        className="block w-full rounded-md border border-gray-300 bg-white py-1.5 pl-8 pr-8 text-sm text-gray-900 placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500"
      />
      {value ? (
        <button
          type="button"
          onClick={() => setValue('')}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
        >
          <XMarkIcon className="size-4" />
        </button>
      ) : null}
    </div>
  )
}
