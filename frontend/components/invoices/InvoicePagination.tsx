import Link from 'next/link'

/** Prev/Next pager for the Invoices list. Server-rendered: the page
 *  computes the hrefs (null = no such page, rendered disabled). */
export function InvoicePagination({
  page,
  pageSize,
  total,
  prevHref,
  nextHref,
}: {
  page: number
  pageSize: number
  total: number
  prevHref: string | null
  nextHref: string | null
}) {
  if (total === 0) return null
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {first.toLocaleString()}–{last.toLocaleString()} of{' '}
        {total.toLocaleString()}
      </p>
      <div className="flex items-center gap-1">
        <PagerButton href={prevHref}>Previous</PagerButton>
        <PagerButton href={nextHref}>Next</PagerButton>
      </div>
    </div>
  )
}

function PagerButton({
  href,
  children,
}: {
  href: string | null
  children: React.ReactNode
}) {
  const base =
    'rounded-md px-2.5 py-1 text-sm font-medium ring-1 ring-inset transition-colors'
  if (href === null) {
    return (
      <span
        aria-disabled="true"
        className={`${base} text-gray-300 ring-gray-200 dark:text-gray-600 dark:ring-white/10`}
      >
        {children}
      </span>
    )
  }
  return (
    <Link
      href={href}
      scroll={false}
      className={`${base} text-gray-700 ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/15 dark:hover:bg-white/5`}
    >
      {children}
    </Link>
  )
}
