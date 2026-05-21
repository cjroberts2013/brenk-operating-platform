'use client'

import {
  useEffect,
  useRef,
  useState,
  useTransition,
} from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/20/solid'

/**
 * The top-bar search input. Scopes itself to whichever list page the
 * user is currently on:
 *
 *   /work-orders  →  searches WO #, location, store id, problem code,
 *                    caller text, description, client name
 *   /vendors      →  searches vendor name, phone, email, service area,
 *                    trade name
 *   anywhere else →  hidden
 *
 * Updates `?q=` on the current URL as the user types (debounced).
 * The list page reads `searchParams.q` server-side and re-fetches —
 * the existing `cache: 'no-store'` on `apiFetch` means no caching to
 * fight with, and the URL becomes copy-pasteable / refresh-stable.
 *
 * Why contextual instead of global: every search a user actually makes
 * on a list page is "narrow this list to what I care about." There's
 * no second results page to design and the URL contract already does
 * everything we need.
 */

/** ms to wait after the last keystroke before pushing the URL. */
const DEBOUNCE_MS = 200

type Scope =
  | { kind: 'searchable'; basePath: string; placeholder: string }
  | { kind: 'hidden' }

function detectScope(pathname: string): Scope {
  // Match the list-page roots only — detail pages (e.g.
  // /work-orders/123) shouldn't filter the parent list out from
  // underneath them, and the search wouldn't have anywhere to apply
  // its `?q=` anyway.
  if (pathname === '/work-orders') {
    return {
      kind: 'searchable',
      basePath: '/work-orders',
      placeholder: 'Search work orders by #, location, problem, caller…',
    }
  }
  if (pathname === '/vendors') {
    return {
      kind: 'searchable',
      basePath: '/vendors',
      placeholder: 'Search vendors by name, phone, email, area, trade…',
    }
  }
  return { kind: 'hidden' }
}

export function ContextualSearch() {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [, startTransition] = useTransition()

  const scope = detectScope(pathname)

  // Controlled input — initialized from the URL on mount and re-synced
  // from the URL on *external* changes (pathname change, paste, back/
  // forward). Internal updates we made ourselves are ignored to avoid
  // overwriting characters the user typed after our last push.
  const [value, setValue] = useState<string>(() => searchParams.get('q') ?? '')

  // Tracks the last `q` we pushed to the URL ourselves. The resync
  // effect compares against this ref to detect "I'm seeing my own
  // push come back" and skip the state overwrite. Initialized to the
  // URL value at mount so a deep link doesn't double-sync.
  const lastPushedRef = useRef<string>(searchParams.get('q') ?? '')

  // Resync local state when the URL changes from a source other than
  // our own debounce (pathname change, browser nav, paste-link).
  //
  // The race we are guarding against: user types fast, debounce pushes
  // an intermediate value to the URL, the server re-fetch takes a few
  // hundred ms, in the meantime the user keeps typing. When the URL
  // change finally propagates, urlValue is "stale" relative to local
  // input. Without the lastPushedRef guard, we would clobber the new
  // characters.
  useEffect(() => {
    const urlValue = searchParams.get('q') ?? ''
    if (urlValue === lastPushedRef.current) return
    lastPushedRef.current = urlValue
    setValue(urlValue)
    // We intentionally do NOT depend on `value` here — only on the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, pathname])

  // Debounced URL push. Replaces the current entry (not pushes) so
  // the back-button doesn't get one history step per typed character.
  useEffect(() => {
    if (scope.kind !== 'searchable') return
    const trimmed = value.trim()
    if (trimmed === lastPushedRef.current) return
    const handle = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString())
      if (trimmed) {
        next.set('q', trimmed)
      } else {
        next.delete('q')
      }
      // Reset pagination when the search changes — the row count
      // shrinks and page=4 is unlikely to still be meaningful.
      next.delete('page')
      const qs = next.toString()
      lastPushedRef.current = trimmed
      startTransition(() => {
        router.replace(qs ? `${scope.basePath}?${qs}` : scope.basePath)
      })
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(handle)
  }, [value, scope, router, searchParams])

  if (scope.kind === 'hidden') {
    // Spacer keeps the header layout consistent across pages — the
    // bell + user menu would otherwise hop left when the search
    // disappeared.
    return <div className="flex-1" aria-hidden="true" />
  }

  function clear() {
    setValue('')
  }

  return (
    <div className="grid flex-1 grid-cols-1">
      <input
        name="search"
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={scope.placeholder}
        aria-label={scope.placeholder}
        autoComplete="off"
        className="col-start-1 row-start-1 block size-full bg-white pl-8 pr-8 text-base text-gray-900 outline-hidden placeholder:text-gray-400 sm:text-sm/6 dark:bg-gray-900 dark:text-white dark:placeholder:text-gray-500"
      />
      <MagnifyingGlassIcon
        aria-hidden="true"
        className="pointer-events-none col-start-1 row-start-1 size-5 self-center text-gray-400"
      />
      {value ? (
        <button
          type="button"
          onClick={clear}
          aria-label="Clear search"
          className="col-start-1 row-start-1 ml-auto mr-2 self-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
        >
          <XMarkIcon className="size-4" />
        </button>
      ) : null}
    </div>
  )
}
