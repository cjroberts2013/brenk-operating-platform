import Link from 'next/link'

import type { InvoiceListItem } from '@/lib/api/types'
import { money, shortDate } from '@/lib/format'

/** Invoice-centric list: one row per actual SC invoice record. */
const STATUS_TONE: Record<string, string> = {
  Paid: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  Approved: 'bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300',
  Rejected: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  Void: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
}
const DEFAULT_TONE =
  'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300'

export function InvoiceListTable({ items }: { items: InvoiceListItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 px-4 py-12 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No invoices yet. They appear here as they&apos;re created in
          ServiceChannel.
        </p>
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <Th>Invoice #</Th>
              <Th>Work order</Th>
              <Th>Location</Th>
              <Th>Status</Th>
              <Th align="right">Billed</Th>
              <Th>Date</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {items.map((inv) => (
              <tr
                key={inv.sc_invoice_id ?? `${inv.invoice_number}-${inv.wo_number}`}
                className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <Td>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {inv.invoice_number}
                  </span>
                </Td>
                <Td>
                  {inv.work_order_id ? (
                    <Link
                      href={`/work-orders/${inv.work_order_id}?from=invoices`}
                      className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                    >
                      {inv.wo_number ?? inv.work_order_id}
                    </Link>
                  ) : (
                    <span className="text-gray-500">{inv.wo_number ?? '—'}</span>
                  )}
                </Td>
                <Td>
                  <div className="text-gray-900 dark:text-white">
                    {inv.location_store_id ?? '—'}
                  </div>
                  {inv.location_name ? (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {inv.location_name}
                    </div>
                  ) : null}
                </Td>
                <Td>
                  {inv.status ? (
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_TONE[inv.status] ?? DEFAULT_TONE
                      }`}
                    >
                      {inv.status}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </Td>
                <Td align="right">
                  <span className="font-medium text-gray-900 dark:text-white">
                    {inv.invoice_total ? money(inv.invoice_total) : '—'}
                  </span>
                </Td>
                <Td>
                  {shortDate(
                    inv.paid_date ??
                      inv.approved_date ??
                      inv.invoice_date ??
                      inv.posted_date,
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Th({
  children,
  align = 'left',
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
}) {
  return (
    <th
      scope="col"
      className={`px-3 py-2 ${
        align === 'right' ? 'text-right' : 'text-left'
      } text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400`}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  align = 'left',
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
}) {
  return (
    <td
      className={`px-3 py-2 ${
        align === 'right' ? 'text-right' : 'text-left'
      } align-top text-sm text-gray-700 dark:text-gray-300`}
    >
      {children}
    </td>
  )
}
