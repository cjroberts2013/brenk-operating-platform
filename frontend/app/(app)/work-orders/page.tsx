import Link from 'next/link'

import { Pagination } from '@/components/work-orders/Pagination'
import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { StatusFilter } from '@/components/work-orders/StatusFilter'
import { SyncWorkOrdersButton } from '@/components/work-orders/SyncWorkOrdersButton'
import {
  getWorkOrderSyncStatus,
  listWorkOrders,
} from '@/lib/api/work-orders'
import { money, relativeTime, shortDate } from '@/lib/format'

const DEFAULT_PAGE_SIZE = 50

type SearchParams = Record<string, string | string[] | undefined>

function parsePositiveInt(
  value: string | string[] | undefined,
  fallback: number,
): number {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return fallback
  const n = Number(raw)
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback
}

function stringParam(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  return raw && raw.length ? raw : undefined
}

export default async function WorkOrdersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const page = parsePositiveInt(sp.page, 1)
  const page_size = parsePositiveInt(sp.page_size, DEFAULT_PAGE_SIZE)
  const status = stringParam(sp.status)
  const q = stringParam(sp.q)

  // Fire list + sync-status in parallel; both are cheap and they're
  // independent of each other.
  const [data, syncStatus] = await Promise.all([
    listWorkOrders({
      page,
      page_size,
      ...(status ? { status } : {}),
      ...(q ? { q } : {}),
    }),
    getWorkOrderSyncStatus(),
  ])

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Work Orders
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {data.total.toLocaleString()} total
            {status ? <> · filtered to <strong>{status}</strong></> : null}
            {q ? <> · matching <strong>“{q}”</strong></> : null} ·
            newest first
          </p>
        </div>
        <StatusFilter current={status} />
      </header>

      <SyncWorkOrdersButton lastSyncedAt={syncStatus.last_synced_at} />

      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        {data.items.length === 0 ? (
          <EmptyState hasFilter={Boolean(status || q)} />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Status</Th>
                  <Th>WO #</Th>
                  <Th>Location</Th>
                  <Th>Trade</Th>
                  <Th>Priority</Th>
                  <Th align="right">NTE</Th>
                  <Th>Scheduled</Th>
                  <Th>Updated</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
                {data.items.map((wo) => (
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
                    <Td>{wo.priority ?? '—'}</Td>
                    <Td align="right">{money(wo.nte)}</Td>
                    <Td>{shortDate(wo.scheduled_date)}</Td>
                    <Td>
                      <span title={wo.sc_updated_date ?? ''}>
                        {relativeTime(wo.sc_updated_date)}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          searchParams={sp}
        />
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

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="px-4 py-16 text-center">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {hasFilter
          ? 'No work orders match the current filter or search.'
          : 'No work orders in the database yet — click Sync now or wait for the hourly sync.'}
      </p>
    </div>
  )
}
