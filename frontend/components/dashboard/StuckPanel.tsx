import Link from 'next/link'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

import { StatusBadge } from '@/components/work-orders/StatusBadge'
import type { StuckWorkOrder } from '@/lib/api/types'
import { relativeTime } from '@/lib/format'

function formatOverdue(days: number): string {
  if (days < 1) return 'just past'
  if (days < 1.5) return '1 day over'
  return `${Math.round(days)} days over`
}

export function StuckPanel({ items }: { items: StuckWorkOrder[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Nothing stuck. Everything in the pipeline is moving on time.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex items-center gap-2 border-b border-gray-200 bg-amber-50/50 px-4 py-2.5 dark:border-white/10 dark:bg-amber-950/20">
        <ExclamationTriangleIcon className="size-4 text-amber-600 dark:text-amber-400" />
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Stuck right now
        </h2>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {items.length} work order{items.length === 1 ? '' : 's'} overdue · most
          overdue first
        </span>
        <Link
          href="/work-orders?stuck=1"
          className="ml-auto text-xs font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
        >
          View all in list
        </Link>
      </header>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <Th>Status</Th>
              <Th>WO #</Th>
              <Th>Stage</Th>
              <Th>Location</Th>
              <Th>Trade</Th>
              <Th>Vendor</Th>
              <Th align="right">Overdue</Th>
              <Th>Last SC update</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {items.map((wo) => (
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
                  <span className="text-xs text-gray-700 dark:text-gray-300">
                    {wo.stage_label}
                  </span>
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
                <Td>
                  {wo.assigned_vendor ? (
                    <Link
                      href={`/vendors/${wo.assigned_vendor.id}`}
                      className="text-gray-700 hover:text-indigo-600 dark:text-gray-300 dark:hover:text-indigo-400"
                    >
                      {wo.assigned_vendor.name}
                    </Link>
                  ) : (
                    <span className="text-xs text-red-600 dark:text-red-400">
                      Unassigned
                    </span>
                  )}
                </Td>
                <Td align="right">
                  <span className="font-medium text-red-700 dark:text-red-400">
                    {formatOverdue(wo.overdue_by_days)}
                  </span>
                </Td>
                <Td>{relativeTime(wo.sc_updated_date)}</Td>
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
