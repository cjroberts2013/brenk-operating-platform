import { ChevronDownIcon, InformationCircleIcon } from '@heroicons/react/20/solid'

import { InvoiceListTable } from '@/components/invoices/InvoiceListTable'
import { InvoicePagination } from '@/components/invoices/InvoicePagination'
import { InvoiceQueueTable } from '@/components/invoices/InvoiceQueueTable'
import { InvoiceSearch } from '@/components/invoices/InvoiceSearch'
import {
  InvoiceStatusTabs,
  type InvoiceStatusTab,
} from '@/components/invoices/InvoiceStatusTabs'
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

// Status buckets for the invoice list. Default to "awaiting" so the Paid
// pile doesn't bury the actionable invoices. 'all' clears the filter.
const INV_STATUS_TABS = [
  { key: 'awaiting', label: 'Awaiting payment' },
  { key: 'paid', label: 'Paid' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'all', label: 'All' },
] as const
type InvStatus = (typeof INV_STATUS_TABS)[number]['key']
const INV_PAGE_SIZE = 15

function parseTab(value: string | string[] | undefined): InvoiceTab {
  const raw = Array.isArray(value) ? value[0] : value
  return (WORKLIST_TABS as string[]).includes(raw ?? '')
    ? (raw as InvoiceTab)
    : 'ready_to_markup'
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function parseInvStatus(value: string | string[] | undefined): InvStatus {
  const raw = first(value)
  return INV_STATUS_TABS.some((t) => t.key === raw)
    ? (raw as InvStatus)
    : 'awaiting'
}

/** Build an /invoices href preserving all current params, applying the
 *  given overrides (undefined deletes the key). */
function hrefWith(
  sp: SearchParams,
  overrides: Record<string, string | undefined>,
): string {
  const next = new URLSearchParams()
  for (const [k, v] of Object.entries(sp)) {
    const s = first(v)
    if (s !== undefined) next.set(k, s)
  }
  for (const [k, v] of Object.entries(overrides)) {
    if (v === undefined) next.delete(k)
    else next.set(k, v)
  }
  const qs = next.toString()
  return qs ? `/invoices?${qs}` : '/invoices'
}

export default async function InvoicesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const tab = parseTab(sp.tab)
  const invStatus = parseInvStatus(sp.inv_status)
  const invQ = first(sp.inv_q)?.trim() || undefined
  const invPage = Math.max(1, Number(first(sp.inv_page)) || 1)

  // A status bucket maps to the API's status_group; 'all' clears it.
  const groupParam = (s: InvStatus) => (s === 'all' ? undefined : s)

  // Active invoice page + per-tab counts (search-aware) + the WO worklist,
  // all in parallel.
  const [invoices, awaitingC, paidC, rejectedC, allC, active, ready, marked] =
    await Promise.all([
      listInvoices({
        status_group: groupParam(invStatus),
        q: invQ,
        page: invPage,
        page_size: INV_PAGE_SIZE,
      }),
      listInvoices({ status_group: 'awaiting', q: invQ, page_size: 1 }),
      listInvoices({ status_group: 'paid', q: invQ, page_size: 1 }),
      listInvoices({ status_group: 'rejected', q: invQ, page_size: 1 }),
      listInvoices({ q: invQ, page_size: 1 }),
      listWorkOrders({ invoice_tab: tab, page_size: 200 }),
      listWorkOrders({ invoice_tab: 'ready_to_markup', page_size: 1 }),
      listWorkOrders({ invoice_tab: 'marked_up', page_size: 1 }),
    ])

  const invCounts: Record<InvStatus, number> = {
    awaiting: awaitingC.total,
    paid: paidC.total,
    rejected: rejectedC.total,
    all: allC.total,
  }

  const statusTabs: InvoiceStatusTab[] = INV_STATUS_TABS.map((t) => ({
    label: t.label,
    count: invCounts[t.key],
    active: t.key === invStatus,
    href: hrefWith(sp, { inv_status: t.key, inv_page: undefined }),
  }))

  const lastPage = Math.max(1, Math.ceil(invoices.total / INV_PAGE_SIZE))
  const prevHref =
    invPage > 1 ? hrefWith(sp, { inv_page: String(invPage - 1) }) : null
  const nextHref =
    invPage < lastPage ? hrefWith(sp, { inv_page: String(invPage + 1) }) : null

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
        count={invCounts.all}
        subtitle="Actual invoices in ServiceChannel, synced live as they're created and as their status changes (Sent → Approved → Paid)."
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <InvoiceStatusTabs tabs={statusTabs} />
          <InvoiceSearch />
        </div>
        <InvoiceListTable
          items={invoices.items}
          emptyMessage={
            invQ
              ? `No invoices match “${invQ}”${
                  invStatus === 'all' ? '' : ' in this status'
                }.`
              : 'No invoices in this status.'
          }
        />
        <InvoicePagination
          page={invPage}
          pageSize={INV_PAGE_SIZE}
          total={invoices.total}
          prevHref={prevHref}
          nextHref={nextHref}
        />
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
