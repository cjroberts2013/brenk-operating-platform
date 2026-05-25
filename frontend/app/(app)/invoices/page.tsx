import { InformationCircleIcon } from '@heroicons/react/20/solid'

import { InvoiceQueueTable } from '@/components/invoices/InvoiceQueueTable'
import {
  InvoiceTabsNav,
  type InvoiceTabCounts,
} from '@/components/invoices/InvoiceTabsNav'
import { listWorkOrders } from '@/lib/api/work-orders'
import {
  INVOICE_TAB_HELP,
  INVOICE_TAB_LABELS,
  type InvoiceTab,
} from '@/lib/api/types'

type SearchParams = Record<string, string | string[] | undefined>

const TABS: InvoiceTab[] = ['ready_to_markup', 'marked_up', 'sent', 'paid']

function parseTab(value: string | string[] | undefined): InvoiceTab {
  const raw = Array.isArray(value) ? value[0] : value
  return (TABS as string[]).includes(raw ?? '')
    ? (raw as InvoiceTab)
    : 'ready_to_markup'
}

export default async function InvoicesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const tab = parseTab(sp.tab)

  // Fetch the active tab's rows + all four tab counts in parallel.
  // The count queries pass page_size=1 — we only need `total`. At our
  // scale the cost is negligible and the layout reads cleanly with
  // counts in the nav.
  const [active, ready, marked, sent, paid] = await Promise.all([
    listWorkOrders({ invoice_tab: tab, page_size: 200 }),
    listWorkOrders({ invoice_tab: 'ready_to_markup', page_size: 1 }),
    listWorkOrders({ invoice_tab: 'marked_up', page_size: 1 }),
    listWorkOrders({ invoice_tab: 'sent', page_size: 1 }),
    listWorkOrders({ invoice_tab: 'paid', page_size: 1 }),
  ])

  const counts: InvoiceTabCounts = {
    ready_to_markup: ready.total,
    marked_up: marked.total,
    sent: sent.total,
    paid: paid.total,
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Invoices
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
          Sue&apos;s clipboard, online. Work orders flow through four stages —
          confirmed by the store → priced by Daryl → invoiced in ServiceChannel
          → paid by the client. Open a work order to set its markup; come back
          here to track what&apos;s where.
        </p>
      </header>

      <InvoiceTabsNav active={tab} counts={counts} />

      {/* Per-tab help. Same place every time so it becomes muscle
          memory rather than something to actively read. */}
      <div className="flex items-start gap-2 rounded-md bg-gray-50 px-3 py-2.5 text-sm text-gray-600 dark:bg-gray-800/40 dark:text-gray-400">
        <InformationCircleIcon className="mt-0.5 size-4 shrink-0 text-gray-400" />
        <p>
          <strong className="font-medium text-gray-900 dark:text-gray-200">
            {INVOICE_TAB_LABELS[tab]}:
          </strong>{' '}
          {INVOICE_TAB_HELP[tab]}
        </p>
      </div>

      <InvoiceQueueTable tab={tab} items={active.items} />

      {active.total > active.items.length ? (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Showing first {active.items.length.toLocaleString()} of{' '}
          {active.total.toLocaleString()}. Open a work order from this list to
          act on it.
        </p>
      ) : null}
    </div>
  )
}
