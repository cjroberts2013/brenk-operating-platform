/**
 * Compact prev/next pagination. Renders only when there's more than
 * one page. Builds the prev/next URLs by cloning the current
 * searchParams and bumping `page`.
 */

import Link from 'next/link'

export function Pagination({
  page,
  pageSize,
  total,
  searchParams,
}: {
  page: number
  pageSize: number
  total: number
  searchParams: Record<string, string | string[] | undefined>
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (totalPages <= 1) return null

  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  function urlForPage(p: number): string {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(searchParams)) {
      if (Array.isArray(v)) params.set(k, v.join(','))
      else if (v != null) params.set(k, v)
    }
    params.set('page', String(p))
    return `?${params.toString()}`
  }

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between border-t border-gray-200 px-4 py-3 dark:border-white/10"
    >
      <p className="text-sm text-gray-700 dark:text-gray-300">
        Showing <span className="font-medium">{start}</span> to{' '}
        <span className="font-medium">{end}</span> of{' '}
        <span className="font-medium">{total}</span>
      </p>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link
            href={urlForPage(page - 1)}
            className="rounded-md bg-white px-3 py-1 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-gray-700"
          >
            Previous
          </Link>
        ) : (
          <span className="rounded-md bg-white px-3 py-1 text-sm font-medium text-gray-400 ring-1 ring-inset ring-gray-200 dark:bg-gray-800 dark:text-gray-600 dark:ring-white/5">
            Previous
          </span>
        )}
        {page < totalPages ? (
          <Link
            href={urlForPage(page + 1)}
            className="rounded-md bg-white px-3 py-1 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-gray-700"
          >
            Next
          </Link>
        ) : (
          <span className="rounded-md bg-white px-3 py-1 text-sm font-medium text-gray-400 ring-1 ring-inset ring-gray-200 dark:bg-gray-800 dark:text-gray-600 dark:ring-white/5">
            Next
          </span>
        )}
      </div>
    </nav>
  )
}
