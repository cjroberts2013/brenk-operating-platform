import Link from 'next/link'

import { INVOICE_TAB_LABELS, type InvoiceTab } from '@/lib/api/types'

const TABS: InvoiceTab[] = ['ready_to_markup', 'marked_up', 'sent', 'paid']

// Per-tab count is shown inline so Sue/Daryl see at a glance where
// the pile is. Computed by the page from parallel calls.
export type InvoiceTabCounts = Record<InvoiceTab, number>

export function InvoiceTabsNav({
  active,
  counts,
}: {
  active: InvoiceTab
  counts: InvoiceTabCounts
}) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-gray-200 dark:border-white/10">
      {TABS.map((tab) => {
        const isActive = tab === active
        return (
          <Link
            key={tab}
            href={`/invoices?tab=${tab}`}
            scroll={false}
            className={
              isActive
                ? 'border-b-2 border-indigo-500 px-3 py-2 text-sm font-medium text-indigo-700 dark:text-indigo-400'
                : 'border-b-2 border-transparent px-3 py-2 text-sm font-medium text-gray-600 hover:border-gray-300 hover:text-gray-800 dark:text-gray-400 dark:hover:border-white/20 dark:hover:text-gray-200'
            }
          >
            {INVOICE_TAB_LABELS[tab]}
            <span
              className={
                isActive
                  ? 'ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300'
                  : 'ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-white/5 dark:text-gray-400'
              }
            >
              {counts[tab]}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
