import Link from 'next/link'
import { notFound } from 'next/navigation'

import { ArrowLeftIcon } from '@heroicons/react/20/solid'

import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { WorkOrderCalendar } from '@/components/work-orders/WorkOrderCalendar'
import { ApiError } from '@/lib/api/server'
import { getVendor } from '@/lib/api/vendors'
import { listWorkOrders } from '@/lib/api/work-orders'
import { money, relativeTime, shortDate } from '@/lib/format'

type SearchParams = Record<string, string | string[] | undefined>

function parseMonth(
  value: string | string[] | undefined,
): { year: number; month: number } {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw && /^\d{4}-\d{2}$/.test(raw)) {
    const [y, m] = raw.split('-').map(Number)
    if (Number.isFinite(y) && Number.isFinite(m) && m >= 1 && m <= 12) {
      return { year: y, month: m - 1 }
    }
  }
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() }
}

function formatContact(value: string | null): string {
  if (!value) return '—'
  if (value === 'sms') return 'Text (SMS)'
  if (value === 'call') return 'Phone call'
  if (value === 'email') return 'Email'
  return value
}

function formatMobileApp(value: boolean | null): string {
  if (value === true) return 'Yes — uses the CubeSmart app'
  if (value === false) return 'No'
  return 'Unknown'
}

export default async function VendorDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<SearchParams>
}) {
  const { id: idStr } = await params
  const id = Number(idStr)
  if (!Number.isFinite(id) || id < 1) notFound()

  const sp = await searchParams
  const { year, month } = parseMonth(sp.month)

  let vendor
  try {
    vendor = await getVendor(id)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }

  // Pull all WOs assigned to this vendor. Page size 200 covers any
  // realistic single-vendor workload; we'll add pagination if we ever
  // see one with more.
  const wos = await listWorkOrders({
    assigned_vendor_id: id,
    page_size: 200,
  })

  return (
    <div className="space-y-6">
      <Link
        href="/vendors"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ArrowLeftIcon className="size-4" />
        Back to Vendors
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            {vendor.name}
            {!vendor.is_active ? (
              <span className="ml-2 align-middle rounded-sm bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 uppercase dark:bg-white/5 dark:text-gray-400">
                Inactive
              </span>
            ) : null}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {vendor.active_work_orders} active work order
            {vendor.active_work_orders === 1 ? '' : 's'} · last updated{' '}
            {relativeTime(vendor.updated_at)}
          </p>
        </div>
      </header>

      <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            Profile
          </h2>
        </header>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 py-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Phone" value={vendor.phone} />
          <Field label="Email" value={vendor.email} />
          <Field
            label="Preferred contact"
            value={formatContact(vendor.contact_preference)}
          />
          <Field label="Payment terms" value={vendor.payment_terms} />
          <Field
            label="Mobile-app capable"
            value={formatMobileApp(vendor.mobile_app_capable)}
          />
          <Field
            label="Trades"
            value={
              vendor.trade_specializations.length === 0
                ? null
                : vendor.trade_specializations.map((t) => t.name).join(', ')
            }
          />
        </dl>
        {vendor.markup_notes ||
        vendor.communication_notes ||
        vendor.notes ? (
          <div className="space-y-3 border-t border-gray-200 px-4 py-4 text-sm dark:border-white/10">
            {vendor.markup_notes ? (
              <NotesBlock label="Markup notes" body={vendor.markup_notes} />
            ) : null}
            {vendor.communication_notes ? (
              <NotesBlock
                label="Communication notes"
                body={vendor.communication_notes}
              />
            ) : null}
            {vendor.notes ? (
              <NotesBlock label="General notes" body={vendor.notes} />
            ) : null}
          </div>
        ) : null}
      </section>

      <section>
        <h2 className="mb-2 text-base font-semibold text-gray-900 dark:text-white">
          Schedule
        </h2>
        <WorkOrderCalendar
          year={year}
          month={month}
          workOrders={wos.items}
          basePath={`/vendors/${id}`}
        />
      </section>

      <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            All assigned work orders
          </h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {wos.total} total. Newest first.
          </p>
        </header>
        {wos.items.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-gray-500 dark:text-gray-400">
            No work orders assigned to this vendor yet.
            <br />
            Assign one from a work order&apos;s detail page (coming next).
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Status</Th>
                  <Th>WO #</Th>
                  <Th>Location</Th>
                  <Th>Trade</Th>
                  <Th align="right">NTE</Th>
                  <Th>Scheduled</Th>
                  <Th>Updated</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
                {wos.items.map((wo) => (
                  <tr
                    key={wo.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <Td>
                      <StatusBadge
                        status={wo.primary_status}
                        extended={wo.extended_status}
                      />
                    </Td>
                    <Td>
                      <Link
                        href={`/work-orders/${wo.id}`}
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
                    <Td align="right">{money(wo.nte)}</Td>
                    <Td>{shortDate(wo.scheduled_date)}</Td>
                    <Td>{relativeTime(wo.sc_updated_date)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function Field({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </dt>
      <dd className="mt-0.5 text-gray-900 dark:text-white">{value || '—'}</dd>
    </div>
  )
}

function NotesBlock({ label, body }: { label: string; body: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </p>
      <p className="mt-0.5 whitespace-pre-wrap text-gray-700 dark:text-gray-300">
        {body}
      </p>
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
