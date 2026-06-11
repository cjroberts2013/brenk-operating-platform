import {
  ArrowTopRightOnSquareIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/20/solid'

import type { InvoiceSummary, WorkOrderDetail } from '@/lib/api/types'
import { money, relativeTime, shortDate } from '@/lib/format'

/**
 * Full read-only view of the WO's ServiceChannel invoice(s), synced from
 * SC invoice webhooks. Renders nothing until an invoice exists in SC.
 * Shows the latest invoice in detail (amounts + lifecycle dates), lists
 * any earlier ones, and links into SC to void / manage.
 */
const STATUS_TONE: Record<string, string> = {
  Paid: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-800',
  Approved: 'bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/40 dark:text-green-300 dark:ring-green-800',
  Rejected: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800',
  Void: 'bg-gray-100 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-white/10',
}
const DEFAULT_TONE =
  'bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:ring-indigo-800'

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
        STATUS_TONE[status] ?? DEFAULT_TONE
      }`}
    >
      {status}
    </span>
  )
}

export function ScInvoiceCard({
  wo,
  scWebUrl,
}: {
  wo: WorkOrderDetail
  scWebUrl: string
}) {
  const invoices = wo.sc_invoices ?? []
  const latest: InvoiceSummary | null = invoices[0] ?? null
  if (!latest && !wo.sc_invoice_number) return null

  const status = latest?.status ?? wo.sc_invoice_status
  const number = latest?.invoice_number ?? wo.sc_invoice_number
  const scLink = `${scWebUrl}/sc/wo/Workorders/index?id=${wo.sc_work_order_id}`

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            ServiceChannel invoice
          </h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            Synced live from SC
          </p>
        </div>
        {invoices.length > 1 ? (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {invoices.length} total
          </span>
        ) : null}
      </header>

      <dl className="space-y-2 px-4 py-3 text-sm">
        <Row label="Invoice #">
          <span className="font-medium text-gray-900 dark:text-white">
            {number ?? '—'}
          </span>
        </Row>
        {status ? (
          <Row label="Status">
            <StatusBadge status={status} />
          </Row>
        ) : null}
        {latest?.invoice_total ? (
          <Row label="Billed total">
            <span className="font-semibold text-gray-900 dark:text-white">
              {money(latest.invoice_total)}
            </span>
          </Row>
        ) : null}
        {latest?.subtotal ? (
          <Row label="Subtotal">{money(latest.subtotal)}</Row>
        ) : null}
        {latest?.invoice_tax && Number(latest.invoice_tax) > 0 ? (
          <Row label="Tax">{money(latest.invoice_tax)}</Row>
        ) : null}
        {latest?.invoice_date ? (
          <Row label="Invoice date">{shortDate(latest.invoice_date)}</Row>
        ) : null}
        {wo.sc_invoice_submitted_at ? (
          <Row label="Submitted">{relativeTime(wo.sc_invoice_submitted_at)}</Row>
        ) : null}
        {latest?.approved_date ? (
          <Row label="Approved">{shortDate(latest.approved_date)}</Row>
        ) : null}
        {(latest?.paid_date ?? wo.sc_paid_at) ? (
          <Row label="Paid">
            {shortDate(latest?.paid_date ?? wo.sc_paid_at)}
          </Row>
        ) : null}
        {latest?.approval_code ? (
          <Row label="Approval code">{latest.approval_code}</Row>
        ) : null}
      </dl>

      {wo.sc_invoice_last_error ? (
        <div className="flex items-start gap-1.5 border-t border-gray-200 px-4 py-2.5 text-xs text-red-700 dark:border-white/10 dark:text-red-300">
          <ExclamationTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{wo.sc_invoice_last_error}</span>
        </div>
      ) : null}

      {invoices.length > 1 ? (
        <div className="border-t border-gray-200 px-4 py-2.5 dark:border-white/10">
          <p className="text-[11px] font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Earlier invoices
          </p>
          <ul className="mt-1 space-y-1">
            {invoices.slice(1).map((inv) => (
              <li
                key={inv.sc_invoice_id ?? inv.invoice_number}
                className="flex items-center justify-between gap-2 text-xs text-gray-600 dark:text-gray-400"
              >
                <span>{inv.invoice_number}</span>
                <span>{inv.status ?? '—'}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="border-t border-gray-200 px-4 py-3 dark:border-white/10">
        <a
          href={scLink}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
        >
          Open in ServiceChannel to void / manage
          <ArrowTopRightOnSquareIcon className="size-4" />
        </a>
      </div>
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
