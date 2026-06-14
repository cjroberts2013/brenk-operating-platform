import Link from 'next/link'

/** Status-bucket tabs for the (invoice-centric) Invoices list. Defaults
 *  to "Awaiting payment" so the Paid pile doesn't bury the actionable
 *  invoices. Counts are shown inline. Pure presentational — the page
 *  builds the hrefs (preserving search + the worklist tab). */
export type InvoiceStatusTab = {
  label: string
  count: number
  href: string
  active: boolean
}

export function InvoiceStatusTabs({ tabs }: { tabs: InvoiceStatusTab[] }) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-gray-200 dark:border-white/10">
      {tabs.map((tab) => (
        <Link
          key={tab.label}
          href={tab.href}
          scroll={false}
          className={
            tab.active
              ? 'border-b-2 border-indigo-500 px-3 py-2 text-sm font-medium text-indigo-700 dark:text-indigo-400'
              : 'border-b-2 border-transparent px-3 py-2 text-sm font-medium text-gray-600 hover:border-gray-300 hover:text-gray-800 dark:text-gray-400 dark:hover:border-white/20 dark:hover:text-gray-200'
          }
        >
          {tab.label}
          <span
            className={
              tab.active
                ? 'ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300'
                : 'ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-white/5 dark:text-gray-400'
            }
          >
            {tab.count.toLocaleString()}
          </span>
        </Link>
      ))}
    </nav>
  )
}
