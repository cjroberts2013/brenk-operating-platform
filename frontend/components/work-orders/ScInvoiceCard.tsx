import { ExclamationTriangleIcon } from '@heroicons/react/20/solid'

import type { WorkOrderDetail } from '@/lib/api/types'
import { relativeTime, shortDate } from '@/lib/format'

/**
 * Read-only summary of the WO's ServiceChannel invoice state, synced from
 * SC invoice webhooks. Renders nothing until an invoice exists in SC, so
 * it stays out of the way on pre-invoice WOs.
 */
const STATUS_TONE: Record<string, string> = {
  Paid: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-800',
  Approved: 'bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/40 dark:text-green-300 dark:ring-green-800',
  Rejected: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800',
  Void: 'bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-white/10',
}
const DEFAULT_TONE =
  'bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:ring-indigo-800'

export function ScInvoiceCard({ wo }: { wo: WorkOrderDetail }) {
  if (!wo.sc_invoice_number && !wo.sc_invoice_status) return null
  const tone = wo.sc_invoice_status
    ? (STATUS_TONE[wo.sc_invoice_status] ?? DEFAULT_TONE)
    : DEFAULT_TONE

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          ServiceChannel invoice
        </h2>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          Synced from SC webhooks
        </p>
      </header>
      <dl className="space-y-2 px-4 py-3 text-sm">
        <Row label="Invoice #">
          <span className="font-medium text-gray-900 dark:text-white">
            {wo.sc_invoice_number ?? '—'}
          </span>
        </Row>
        {wo.sc_invoice_status ? (
          <Row label="Status">
            <span
              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}
            >
              {wo.sc_invoice_status}
            </span>
          </Row>
        ) : null}
        {wo.sc_invoice_submitted_at ? (
          <Row label="Submitted">{relativeTime(wo.sc_invoice_submitted_at)}</Row>
        ) : null}
        {wo.sc_paid_at ? <Row label="Paid">{shortDate(wo.sc_paid_at)}</Row> : null}
      </dl>
      {wo.sc_invoice_last_error ? (
        <div className="flex items-start gap-1.5 border-t border-gray-200 px-4 py-2.5 text-xs text-red-700 dark:border-white/10 dark:text-red-300">
          <ExclamationTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{wo.sc_invoice_last_error}</span>
        </div>
      ) : null}
    </section>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="text-right text-gray-700 dark:text-gray-300">{children}</dd>
    </div>
  )
}
