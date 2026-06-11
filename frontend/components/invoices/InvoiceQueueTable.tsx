import Link from 'next/link'

import type { InvoiceTab, WorkOrderSummary } from '@/lib/api/types'
import { money, relativeTime, shortDate } from '@/lib/format'

/** Per-tab column config. The first three columns (WO# / Location /
 *  Trade) are universal; the rest follow Sue's mental model — what
 *  she'd want to see for *this* pile of work right now. */
type ColumnKey =
  | 'vendor'
  | 'vendor_cost'
  | 'markup'
  | 'total_bill'
  | 'marked_up_at'
  | 'sent_at'
  | 'paid_at'
  | 'updated'
  | 'sc_invoice'
  | 'sc_status'
  | 'sc_total'
  | 'sc_error'

const COLUMNS_BY_TAB: Record<InvoiceTab, ColumnKey[]> = {
  ready_to_markup: ['vendor', 'vendor_cost', 'updated'],
  marked_up: ['vendor', 'vendor_cost', 'markup', 'total_bill', 'marked_up_at'],
  // Post-submit tabs lead with the real SC invoice (synced from webhooks).
  sent: ['vendor', 'sc_invoice', 'sc_status', 'sc_total', 'sent_at'],
  rejected: ['vendor', 'sc_invoice', 'sc_status', 'sc_error'],
  paid: ['vendor', 'sc_invoice', 'sc_total', 'paid_at'],
}

const RIGHT_ALIGNED: ReadonlySet<ColumnKey> = new Set([
  'vendor_cost',
  'total_bill',
  'sc_total',
])

const COLUMN_LABELS: Record<ColumnKey, string> = {
  vendor: 'Vendor',
  vendor_cost: 'Vendor cost',
  markup: 'Markup',
  total_bill: 'Total bill',
  marked_up_at: 'Marked up',
  sent_at: 'Submitted',
  paid_at: 'Paid',
  updated: 'Updated',
  sc_invoice: 'Invoice #',
  sc_status: 'SC status',
  sc_total: 'Billed',
  sc_error: 'Reason',
}

const SC_STATUS_TONE: Record<string, string> = {
  Paid: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  Approved: 'bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300',
  Rejected: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  Void: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
}

/** Sum of labor + material costs Brenk owes the vendor. Either may
 *  be null; treat that as 0 for the sum. Returns null only when
 *  *both* are null (i.e. nothing entered yet). */
function vendorSubtotal(
  labor: string | null,
  material: string | null,
): number | null {
  if (labor === null && material === null) return null
  const l = labor ? Number(labor) : 0
  const m = material ? Number(material) : 0
  if (!Number.isFinite(l) || !Number.isFinite(m)) return null
  return l + m
}

function totalBill(
  labor: string | null,
  material: string | null,
  markup: string | null,
): string | null {
  // Total = (labor + material) * (1 + markup/100). Uses Brenk's
  // internal vendor cost — NOT NTE. NTE is the client-side ceiling,
  // a separate number, never the cost basis for markup.
  const subtotal = vendorSubtotal(labor, material)
  if (subtotal === null) return null
  const pct = Number(markup ?? '0')
  if (!Number.isFinite(pct)) return null
  return (subtotal * (1 + pct / 100)).toFixed(2)
}

function CellValue({
  column,
  wo,
}: {
  column: ColumnKey
  wo: WorkOrderSummary
}) {
  switch (column) {
    case 'vendor':
      return wo.assigned_vendor ? (
        <Link
          href={`/vendors/${wo.assigned_vendor.id}`}
          className="text-gray-700 hover:text-indigo-600 dark:text-gray-300 dark:hover:text-indigo-400"
        >
          {wo.assigned_vendor.name}
        </Link>
      ) : (
        <span className="text-xs text-red-600 dark:text-red-400">Unassigned</span>
      )
    case 'vendor_cost': {
      // Brenk-private. Sum of labor + material. Empty until Daryl/Sue
      // enters them after the vendor sends Brenk a bill.
      const subtotal = vendorSubtotal(
        wo.brenk_labor_cost,
        wo.brenk_material_cost,
      )
      return subtotal !== null && subtotal > 0 ? (
        <>{money(subtotal.toFixed(2))}</>
      ) : (
        <span className="text-xs text-amber-600 dark:text-amber-400">
          Awaiting vendor bill
        </span>
      )
    }
    case 'markup':
      return wo.brenk_markup_percent ? (
        <span className="font-medium text-gray-900 dark:text-white">
          {Number(wo.brenk_markup_percent).toFixed(0)}%
        </span>
      ) : (
        <span className="text-gray-400">—</span>
      )
    case 'total_bill':
      return (
        <span className="font-medium text-gray-900 dark:text-white">
          {money(
            totalBill(
              wo.brenk_labor_cost,
              wo.brenk_material_cost,
              wo.brenk_markup_percent,
            ),
          )}
        </span>
      )
    case 'marked_up_at':
      return <>{relativeTime(wo.brenk_marked_up_at)}</>
    case 'sent_at':
      return <>{relativeTime(wo.sc_invoice_submitted_at ?? wo.sc_updated_date)}</>
    case 'paid_at':
      return <>{shortDate(wo.sc_paid_at ?? wo.brenk_paid_at)}</>
    case 'updated':
      return <>{relativeTime(wo.sc_updated_date)}</>
    case 'sc_invoice':
      return wo.sc_invoice_number ? (
        <span className="font-medium text-gray-900 dark:text-white">
          {wo.sc_invoice_number}
        </span>
      ) : (
        <span className="text-gray-400">—</span>
      )
    case 'sc_status':
      return wo.sc_invoice_status ? (
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
            SC_STATUS_TONE[wo.sc_invoice_status] ??
            'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300'
          }`}
        >
          {wo.sc_invoice_status}
        </span>
      ) : (
        <span className="text-gray-400">—</span>
      )
    case 'sc_total':
      return (
        <span className="font-medium text-gray-900 dark:text-white">
          {wo.sc_invoice_total ? money(wo.sc_invoice_total) : '—'}
        </span>
      )
    case 'sc_error':
      return wo.sc_invoice_last_error ? (
        <span className="text-xs text-red-700 dark:text-red-300">
          {wo.sc_invoice_last_error}
        </span>
      ) : (
        <span className="text-gray-400">—</span>
      )
  }
}

export function InvoiceQueueTable({
  tab,
  items,
}: {
  tab: InvoiceTab
  items: WorkOrderSummary[]
}) {
  const columns = COLUMNS_BY_TAB[tab]
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 px-4 py-12 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Nothing in this tab right now.
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
              <Th>WO #</Th>
              <Th>Location</Th>
              <Th>Trade</Th>
              {columns.map((c) => (
                <Th key={c} align={RIGHT_ALIGNED.has(c) ? 'right' : 'left'}>
                  {COLUMN_LABELS[c]}
                </Th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {items.map((wo) => (
              <tr
                key={wo.id}
                className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <Td>
                  <Link
                    href={`/work-orders/${wo.id}?from=invoices`}
                    className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                  >
                    {wo.sc_number}
                  </Link>
                </Td>
                <Td>
                  <div className="text-gray-900 dark:text-white">
                    {wo.location?.store_id ?? '—'}
                  </div>
                  {wo.location?.name ? (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {wo.location.name}
                    </div>
                  ) : null}
                </Td>
                <Td>{wo.trade?.name ?? '—'}</Td>
                {columns.map((c) => (
                  <Td
                    key={c}
                    align={RIGHT_ALIGNED.has(c) ? 'right' : 'left'}
                  >
                    <CellValue column={c} wo={wo} />
                  </Td>
                ))}
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
