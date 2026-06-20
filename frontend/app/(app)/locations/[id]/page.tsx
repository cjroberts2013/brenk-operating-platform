import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeftIcon } from '@heroicons/react/20/solid'

import { GateCodesPanel } from '@/components/locations/GateCodesPanel'
import { LocationEditButton } from '@/components/locations/LocationEditButton'
import { RatingBadge } from '@/components/locations/RatingBadge'
import { Pagination } from '@/components/work-orders/Pagination'
import { getLocation, listLocationWorkOrders } from '@/lib/api/locations'
import { ApiError } from '@/lib/api/server'
import type { WorkOrderListResponse, WorkOrderSummary } from '@/lib/api/types'

type SearchParams = Record<string, string | string[] | undefined>

const WO_PAGE_SIZE = 20

function parsePositiveInt(
  value: string | string[] | undefined,
  fallback: number,
): number {
  const raw = Array.isArray(value) ? value[0] : value
  const n = Number(raw)
  return Number.isInteger(n) && n > 0 ? n : fallback
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default async function LocationDetailPage({
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
  const woPage = parsePositiveInt(sp.page, 1)

  let location
  let workOrders: WorkOrderListResponse
  try {
    ;[location, workOrders] = await Promise.all([
      getLocation(id),
      listLocationWorkOrders(id, { page: woPage, page_size: WO_PAGE_SIZE }),
    ])
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }

  const title = location.name ?? `Location ${location.sc_location_id}`

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/locations"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <ArrowLeftIcon className="size-4" />
          Back to Locations
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
              {title}
            </h1>
            <RatingBadge rating={location.rating} />
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {location.store_id ? <>Store {location.store_id} · </> : null}
            {location.address ?? 'No address on file'}
          </p>
        </div>
        <LocationEditButton location={location} />
      </header>

      {/* Metric tiles */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Metric label="Active work orders" value={location.active_work_orders} />
        <Metric label="Total work orders" value={location.total_work_orders} />
        <Metric
          label="Last activity"
          value={formatDate(location.last_work_order_date)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: details + related WOs */}
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
            <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                Details
              </h2>
            </header>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 py-4 text-sm sm:grid-cols-2">
              <Field label="District" value={location.district} />
              <Field label="Region" value={location.region} />
              <Field
                label="District manager"
                value={location.district_manager_name}
              />
              <Field
                label="Manager phone"
                value={location.district_manager_phone}
              />
              <Field
                label="Manager email"
                value={location.district_manager_email}
              />
              <Field label="Address" value={location.address} />
            </dl>
            {location.description ? (
              <div className="border-t border-gray-200 px-4 py-4 dark:border-white/10">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Notes
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                  {location.description}
                </p>
              </div>
            ) : null}
          </section>

          <section>
            <h2 className="mb-2 text-base font-semibold text-gray-900 dark:text-white">
              Work orders at this location
              <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                {location.total_work_orders} total
              </span>
            </h2>
            <RelatedWorkOrders
              workOrders={workOrders.items}
              page={workOrders.page}
              pageSize={workOrders.page_size}
              total={workOrders.total}
              searchParams={sp}
            />
          </section>
        </div>

        {/* Right: gate codes */}
        <div className="space-y-6">
          <GateCodesPanel
            locationId={location.id}
            active={location.gate_codes_active}
            history={location.gate_codes_history}
          />
        </div>
      </div>
    </div>
  )
}

function RelatedWorkOrders({
  workOrders,
  page,
  pageSize,
  total,
  searchParams,
}: {
  workOrders: WorkOrderSummary[]
  page: number
  pageSize: number
  total: number
  searchParams: SearchParams
}) {
  if (workOrders.length === 0) {
    return (
      <div className="rounded-lg px-4 py-10 text-center ring-1 ring-gray-200 dark:ring-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No work orders at this location yet.
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
              <Th>Status</Th>
              <Th>Trade</Th>
              <Th>Vendor</Th>
              <Th align="right">Updated</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {workOrders.map((wo) => (
              <tr
                key={wo.id}
                className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <Td>
                  <Link
                    href={`/work-orders/${wo.id}`}
                    className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                  >
                    {wo.sc_number}
                  </Link>
                  {wo.is_stuck ? (
                    <span className="ml-2 rounded-sm bg-red-100 px-1.5 py-px text-[10px] font-medium text-red-700 uppercase dark:bg-red-950 dark:text-red-300">
                      Stuck
                    </span>
                  ) : null}
                </Td>
                <Td>
                  {wo.primary_status}
                  {wo.extended_status ? (
                    <span className="text-gray-400"> / {wo.extended_status}</span>
                  ) : null}
                </Td>
                <Td>{wo.trade?.name ?? '—'}</Td>
                <Td>{wo.assigned_vendor?.name ?? '—'}</Td>
                <Td align="right">{formatDate(wo.sc_updated_date)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        searchParams={searchParams}
      />
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg px-4 py-3 ring-1 ring-gray-200 dark:ring-white/10">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
        {value}
      </p>
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
