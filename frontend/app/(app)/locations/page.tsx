import Link from 'next/link'
import { ArrowDownTrayIcon } from '@heroicons/react/20/solid'

import { RatingBadge } from '@/components/locations/RatingBadge'
import { Pagination } from '@/components/work-orders/Pagination'
import { listLocations } from '@/lib/api/locations'

type SearchParams = Record<string, string | string[] | undefined>

const DEFAULT_PAGE_SIZE = 50
const RATINGS = ['good', 'watch', 'problem'] as const

function stringParam(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  return raw && raw.length ? raw : undefined
}

function parsePositiveInt(
  value: string | string[] | undefined,
  fallback: number,
): number {
  const raw = Array.isArray(value) ? value[0] : value
  const n = Number(raw)
  return Number.isInteger(n) && n > 0 ? n : fallback
}

/** Build the `?q=&rating=` suffix for the export link so a download
 *  matches the currently-filtered view. Empty string when unfiltered. */
function exportQuery(q?: string, rating?: string): string {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (rating) params.set('rating', rating)
  const s = params.toString()
  return s ? `?${s}` : ''
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default async function LocationsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const page = parsePositiveInt(sp.page, 1)
  const q = stringParam(sp.q)
  const ratingRaw = stringParam(sp.rating)
  const rating = RATINGS.includes(ratingRaw as (typeof RATINGS)[number])
    ? ratingRaw
    : undefined

  const data = await listLocations({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    ...(q ? { q } : {}),
    ...(rating ? { rating } : {}),
  })

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Locations
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Stores synced from ServiceChannel work orders. Track the district
            manager, gate codes, a health rating, and running notes per site.{' '}
            {data.total} total
            {q ? (
              <>
                {' '}
                · matching <strong>“{q}”</strong>
              </>
            ) : null}
            {rating ? <> · rated {rating}</> : null}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href={`/locations/export${exportQuery(q, rating)}`}
            className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-xs ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-white/5 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/10"
          >
            <ArrowDownTrayIcon className="size-4" />
            Download Excel
          </a>
          <RatingFilter current={rating} />
        </div>
      </header>

      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        {data.items.length === 0 ? (
          <div className="px-4 py-16 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No locations found. They appear automatically as work orders
              sync from ServiceChannel.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Store</Th>
                  <Th>Name</Th>
                  <Th>District</Th>
                  <Th>District manager</Th>
                  <Th>Rating</Th>
                  <Th align="right">Active WOs</Th>
                  <Th align="right">Total WOs</Th>
                  <Th align="right">Last activity</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
                {data.items.map((loc) => (
                  <tr
                    key={loc.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <Td>{loc.store_id ?? '—'}</Td>
                    <Td>
                      <Link
                        href={`/locations/${loc.id}`}
                        className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                      >
                        {loc.name ?? `Location ${loc.sc_location_id}`}
                      </Link>
                    </Td>
                    <Td>{loc.district ?? '—'}</Td>
                    <Td>{loc.district_manager_name ?? '—'}</Td>
                    <Td>
                      <RatingBadge rating={loc.rating} />
                    </Td>
                    <Td align="right">{loc.active_work_orders}</Td>
                    <Td align="right">{loc.total_work_orders}</Td>
                    <Td align="right">{formatDate(loc.last_work_order_date)}</Td>
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

function RatingFilter({ current }: { current: string | undefined }) {
  return (
    <div className="inline-flex rounded-md ring-1 ring-gray-300 dark:ring-white/10">
      <FilterLink href="/locations" active={current === undefined}>
        All
      </FilterLink>
      <FilterLink href="/locations?rating=good" active={current === 'good'}>
        Good
      </FilterLink>
      <FilterLink href="/locations?rating=watch" active={current === 'watch'}>
        Watch
      </FilterLink>
      <FilterLink href="/locations?rating=problem" active={current === 'problem'}>
        Problem
      </FilterLink>
    </div>
  )
}

function FilterLink({
  href,
  active,
  children,
}: {
  href: string
  active: boolean
  children: React.ReactNode
}) {
  return (
    <a
      href={href}
      className={`px-3 py-1.5 text-sm font-medium first:rounded-l-md last:rounded-r-md ${
        active
          ? 'bg-indigo-500 text-white'
          : 'bg-white text-gray-700 hover:bg-gray-50 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-white/5'
      }`}
    >
      {children}
    </a>
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
