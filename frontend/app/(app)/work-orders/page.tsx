import Link from 'next/link'
import {
  ExclamationTriangleIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/react/20/solid'

import { CategoryCell } from '@/components/work-orders/CategoryCell'
import { DeadlineBadge } from '@/components/work-orders/DeadlineBadge'
import { Pagination } from '@/components/work-orders/Pagination'
import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { StatusFilter } from '@/components/work-orders/StatusFilter'
import { SyncWorkOrdersButton } from '@/components/work-orders/SyncWorkOrdersButton'
import {
  getWorkOrderSyncStatus,
  listWorkOrders,
} from '@/lib/api/work-orders'
import {
  DEADLINE_FILTER_LABELS,
  STAGE_LABELS,
  type DeadlineFilterKey,
  type PipelineStageKey,
} from '@/lib/api/types'
import { money, relativeTime, shortDate } from '@/lib/format'

const DEFAULT_PAGE_SIZE = 50

const STAGE_KEYS = Object.keys(STAGE_LABELS) as PipelineStageKey[]

const DEADLINE_KEYS = Object.keys(
  DEADLINE_FILTER_LABELS,
) as DeadlineFilterKey[]

function parseStage(
  value: string | string[] | undefined,
): PipelineStageKey | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return undefined
  return (STAGE_KEYS as string[]).includes(raw)
    ? (raw as PipelineStageKey)
    : undefined
}

function parseDeadline(
  value: string | string[] | undefined,
): DeadlineFilterKey | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return undefined
  return (DEADLINE_KEYS as string[]).includes(raw)
    ? (raw as DeadlineFilterKey)
    : undefined
}

type SearchParams = Record<string, string | string[] | undefined>

/** Whether a sub-vendor should already be assigned at this WO's stage.
 *  Pre-acceptance WOs don't need one yet, and terminal canceled /
 *  no-charge WOs never will — only highlight "Unassigned" in red where
 *  it's an actual gap (work dispatched, in flight, or billable). */
function vendorExpected(wo: {
  primary_status: string
  extended_status: string | null
}): boolean {
  const p = wo.primary_status.toUpperCase()
  const e = (wo.extended_status ?? '').toUpperCase()
  if (p === 'IN PROGRESS') return e !== 'WAITING FOR APPROVAL'
  if (p === 'COMPLETED') return e !== 'CANCELED' && e !== 'NO CHARGE'
  return false
}

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
  review?: boolean
  deadline?: string
}): string {
  const p = new URLSearchParams()
  if (params.status) p.set('status', params.status)
  if (params.q) p.set('q', params.q)
  if (params.stage) p.set('stage', params.stage)
  if (params.stuck) p.set('stuck', '1')
  if (params.review) p.set('category_review', '1')
  if (params.deadline) p.set('deadline', params.deadline)
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
  const review = parseBool(sp.category_review)
  const deadline = parseDeadline(sp.deadline)

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
      ...(review ? { category_review: true } : {}),
      ...(deadline ? { deadline } : {}),
    }),
    getWorkOrderSyncStatus(),
  ])

  // Dropping a filter expands the result set, so each "clear" link
  // also resets pagination by omitting `page`.
  const clearStageHref = buildHref({ status, q, stuck, review, deadline })
  const clearStuckHref = buildHref({ status, q, stage, review, deadline })
  const toggleStuckHref = buildHref({
    status,
    q,
    stage,
    stuck: !stuck,
    review,
    deadline,
  })
  const clearReviewHref = buildHref({ status, q, stage, stuck, deadline })
  const toggleReviewHref = buildHref({
    status,
    q,
    stage,
    stuck,
    review: !review,
    deadline,
  })
  const clearDeadlineHref = buildHref({ status, q, stage, stuck, review })

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
            {stuck ? <> · <strong>stuck</strong> only</> : null}
            {review ? <> · <strong>category needs review</strong></> : null}
            {deadline ? (
              <> · <strong>{DEADLINE_FILTER_LABELS[deadline].toLowerCase()}</strong></>
            ) : null} ·
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
          <Link
            href={toggleReviewHref}
            title={
              review
                ? 'Show all work orders'
                : 'Show only WOs whose category is AI-suggested and not yet confirmed'
            }
            className={
              review
                ? 'inline-flex items-center gap-1.5 rounded-md bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 ring-1 ring-inset ring-amber-200 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800'
                : 'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5'
            }
          >
            <SparklesIcon className="size-4" />
            {review ? 'Showing needs-review' : 'Needs review'}
          </Link>
          <StatusFilter current={status} />
        </div>
      </header>

      {stage || stuck || review || deadline ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Active filter{[stage, stuck, review, deadline].filter(Boolean).length > 1 ? 's' : ''}:
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
          {review ? (
            <Link
              href={clearReviewHref}
              title="Clear category-review filter"
              className="group inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800"
            >
              Category needs review
              <XMarkIcon className="size-3 text-amber-400 transition group-hover:text-amber-700 dark:text-amber-500 dark:group-hover:text-amber-300" />
            </Link>
          ) : null}
          {deadline ? (
            <Link
              href={clearDeadlineHref}
              title="Clear deadline filter"
              className="group inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-100 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800"
            >
              {DEADLINE_FILTER_LABELS[deadline]}
              <XMarkIcon className="size-3 text-red-400 transition group-hover:text-red-700 dark:text-red-500 dark:group-hover:text-red-300" />
            </Link>
          ) : null}
        </div>
      ) : null}

      <SyncWorkOrdersButton lastSyncedAt={syncStatus.last_synced_at} />

      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        {data.items.length === 0 ? (
          <EmptyState
            hasFilter={Boolean(status || q || stage || stuck || review || deadline)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Status</Th>
                  <Th>WO #</Th>
                  <Th>Location</Th>
                  <Th>Trade</Th>
                  <Th>Category</Th>
                  <Th>Vendor</Th>
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
                        <DeadlineBadge
                          urgency={wo.deadline_urgency}
                          daysPast={wo.deadline_days_past}
                        />
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
                    <Td>
                      <CategoryCell
                        category={wo.brenk_category}
                        source={wo.brenk_category_source}
                        confidence={wo.brenk_category_confidence}
                      />
                    </Td>
                    <Td>
                      {wo.assigned_vendor ? (
                        <span className="inline-flex items-center gap-1">
                          <Link
                            href={`/vendors/${wo.assigned_vendor.id}`}
                            className="text-gray-700 hover:text-indigo-600 dark:text-gray-300 dark:hover:text-indigo-400"
                          >
                            {wo.assigned_vendor.name}
                          </Link>
                          {wo.vendor_assignments.length > 1 ? (
                            <span
                              className="rounded-sm bg-gray-100 px-1 text-[10px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-400"
                              title={`${wo.vendor_assignments.length} vendors assigned`}
                            >
                              +{wo.vendor_assignments.length - 1}
                            </span>
                          ) : null}
                        </span>
                      ) : vendorExpected(wo) ? (
                        <span className="text-xs font-medium text-red-600 dark:text-red-400">
                          Unassigned
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          Unassigned
                        </span>
                      )}
                    </Td>
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
