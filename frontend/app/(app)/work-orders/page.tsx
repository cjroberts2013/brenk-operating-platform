import Link from 'next/link'
import { ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/20/solid'

import { Pagination } from '@/components/work-orders/Pagination'
import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { StatusFilter } from '@/components/work-orders/StatusFilter'
import { SyncWorkOrdersButton } from '@/components/work-orders/SyncWorkOrdersButton'
import {
  getWorkOrderSyncStatus,
  listWorkOrders,
} from '@/lib/api/work-orders'
import { STAGE_LABELS, type PipelineStageKey } from '@/lib/api/types'
import { money, relativeTime, shortDate } from '@/lib/format'

const DEFAULT_PAGE_SIZE = 50

const STAGE_KEYS = Object.keys(STAGE_LABELS) as PipelineStageKey[]

function parseStage(
  value: string | string[] | undefined,
): PipelineStageKey | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return undefined
  return (STAGE_KEYS as string[]).includes(raw)
    ? (raw as PipelineStageKey)
    : undefined
}

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

function parseBool(value: string | string[] | undefined): boolean {
  const raw = Array.isArray(value) ? value[0] : value
  return raw === '1' || raw === 'true'
}

/** Build a /work-orders URL preserving the active filters. */
function buildHref(params: {
  status?: string
  q?: string
  stage?: string
  stuck?: boolean
}): string {
  const p = new URLSearchParams()
  if (params.status) p.set('status', params.status)
  if (params.q) p.set('q', params.q)
  if (params.stage) p.set('stage', params.stage)
  if (params.stuck) p.set('stuck', '1')
  const qs = p.toString()
  return qs ? `/work-orders?${qs}` : '/work-orders'
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
  const stage = parseStage(sp.stage)
  const stuck = parseBool(sp.stuck)

  // Fire list + sync-status in parallel; both are cheap and they're
  // independent of each other.
  const [data, syncStatus] = await Promise.all([
    listWorkOrders({
      page,
      page_size,
      ...(status ? { status } : {}),
      ...(q ? { q } : {}),
      ...(stage ? { stage } : {}),
      ...(stuck ? { stuck: true } : {}),
    }),
    getWorkOrderSyncStatus(),
  ])

  // Dropping a filter expands the result set, so each "clear" link
  // also resets pagination by omitting `page`.
  const clearStageHref = buildHref({ status, q, stuck })
  const clearStuckHref = buildHref({ status, q, stage })
  const toggleStuckHref = buildHref({ status, q, stage, stuck: !stuck })

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Work Orders
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {data.total.toLocaleString()} total
            {stage ? (
              <>
                {' '}
                · in stage <strong>{STAGE_LABELS[stage]}</strong>
              </>
            ) : null}
            {status ? <> · filtered to <strong>{status}</strong></> : null}
            {q ? <> · matching <strong>“{q}”</strong></> : null}
            {stuck ? <> · <strong>stuck</strong> only</> : null} ·
            newest first
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={toggleStuckHref}
            title={stuck ? 'Show all work orders' : 'Show only stalled work orders'}
            className={
              stuck
                ? 'inline-flex items-center gap-1.5 rounded-md bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-100 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800'
                : 'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5'
            }
          >
            <ExclamationTriangleIcon className="size-4" />
            {stuck ? 'Showing stuck' : 'Stuck only'}
          </Link>
          <StatusFilter current={status} />
        </div>
      </header>

      {stage || stuck ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Active filter{stage && stuck ? 's' : ''}:
          </span>
          {stage ? (
            <Link
              href={clearStageHref}
              title="Clear stage filter"
              className="group inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300 dark:ring-indigo-800"
            >
              Stage: {STAGE_LABELS[stage]}
              <XMarkIcon className="size-3 text-indigo-400 transition group-hover:text-indigo-700 dark:text-indigo-500 dark:group-hover:text-indigo-300" />
            </Link>
          ) : null}
          {stuck ? (
            <Link
              href={clearStuckHref}
              title="Clear stuck filter"
              className="group inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-100 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800"
            >
              Stuck only
              <XMarkIcon className="size-3 text-red-400 transition group-hover:text-red-700 dark:text-red-500 dark:group-hover:text-red-300" />
            </Link>
          ) : null}
        </div>
      ) : null}

      <SyncWorkOrdersButton lastSyncedAt={syncStatus.last_synced_at} />

      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        {data.items.length === 0 ? (
          <EmptyState hasFilter={Boolean(status || q || stage || stuck)} />
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
                      <div className="flex flex-col items-start gap-1">
                        <StatusBadge
                          status={wo.primary_status}
                          extended={wo.extended_status}
                        />
                        {wo.is_stuck ? (
                          <span className="inline-flex items-center gap-0.5 rounded-sm bg-red-50 px-1.5 py-px text-[10px] font-medium uppercase text-red-700 dark:bg-red-950/50 dark:text-red-400">
                            <ExclamationTriangleIcon className="size-2.5" />
                            Stuck
                          </span>
                        ) : null}
                      </div>
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
