import { ChevronDownIcon, InformationCircleIcon } from '@heroicons/react/20/solid'

import { InvoiceListTable } from '@/components/invoices/InvoiceListTable'
import { InvoiceQueueTable } from '@/components/invoices/InvoiceQueueTable'
import {
  InvoiceTabsNav,
  type InvoiceTabCounts,
} from '@/components/invoices/InvoiceTabsNav'
import { listInvoices } from '@/lib/api/invoices'
import { listWorkOrders } from '@/lib/api/work-orders'
import {
  INVOICE_TAB_HELP,
  INVOICE_TAB_LABELS,
  type InvoiceTab,
} from '@/lib/api/types'

type SearchParams = Record<string, string | string[] | undefined>

// The worklist covers only the pre-invoice WO states. Once an invoice
// exists in SC, the WO leaves the worklist and appears in the Invoices
// list (which is invoice-centric).
const WORKLIST_TABS: InvoiceTab[] = ['ready_to_markup', 'marked_up']

function parseTab(value: string | string[] | undefined): InvoiceTab {
  const raw = Array.isArray(value) ? value[0] : value
  return (WORKLIST_TABS as string[]).includes(raw ?? '')
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

  // Invoice list (invoice-centric) + the WO worklist active tab + counts,
  // all in parallel.
  const [invoices, active, ready, marked] = await Promise.all([
    listInvoices({ page_size: 200 }),
    listWorkOrders({ invoice_tab: tab, page_size: 200 }),
    listWorkOrders({ invoice_tab: 'ready_to_markup', page_size: 1 }),
    listWorkOrders({ invoice_tab: 'marked_up', page_size: 1 }),
  ])

  const counts: InvoiceTabCounts = {
    ready_to_markup: ready.total,
    marked_up: marked.total,
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Invoices
        </h1>
      </header>

      {/* Section 1: actual SC invoices (invoice-centric). */}
      <Section
        title="Invoices"
        count={invoices.total}
        subtitle="Actual invoices in ServiceChannel, synced live as they're created and as their status changes (Sent → Approved → Paid)."
      >
        <InvoiceListTable items={invoices.items} />
        {invoices.total > invoices.items.length ? (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Showing first {invoices.items.length.toLocaleString()} of{' '}
            {invoices.total.toLocaleString()}.
          </p>
        ) : null}
      </Section>

      {/* Section 2: the WO billing worklist (pre-invoice). */}
      <Section
        title="Work orders to invoice"
        count={(counts.ready_to_markup ?? 0) + (counts.marked_up ?? 0)}
        subtitle="Completed work orders that still need pricing and submitting to ServiceChannel. These don't have an invoice yet."
      >
        <InvoiceTabsNav active={tab} counts={counts} />

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
            {active.total.toLocaleString()}. Open a work order to act on it.
          </p>
        ) : null}
      </Section>
    </div>
  )
}

/** Collapsible section with a heading, count, and subtitle. Default open;
 *  native <details> so it works in a server component. */
function Section({
  title,
  count,
  subtitle,
  children,
}: {
  title: string
  count: number
  subtitle: string
  children: React.ReactNode
}) {
  return (
    <details open className="group">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3 [&::-webkit-details-marker]:hidden">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            {title}
            <span className="ml-1.5 text-sm font-normal text-gray-500 dark:text-gray-400">
              {count.toLocaleString()}
            </span>
          </h2>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            {subtitle}
          </p>
        </div>
        <ChevronDownIcon className="mt-1 size-5 shrink-0 text-gray-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-4 space-y-4">{children}</div>
    </details>
  )
}
