import { VendorsTableWithActions } from '@/components/vendors/VendorsTableWithActions'
import { listTrades } from '@/lib/api/trades'
import { listVendors } from '@/lib/api/vendors'

type SearchParams = Record<string, string | string[] | undefined>

function parseBool(
  value: string | string[] | undefined,
): boolean | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === 'true') return true
  if (raw === 'false') return false
  return undefined
}

function stringParam(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  return raw && raw.length ? raw : undefined
}

export default async function VendorsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const is_active = parseBool(sp.is_active)
  const q = stringParam(sp.q)

  // Default to "active only" unless the user explicitly asks otherwise.
  // Tracked in the URL so reloads + back/forward keep the same view.
  const effectiveFilter = is_active === undefined ? true : is_active

  const [vendors, trades] = await Promise.all([
    listVendors({
      page_size: 200,
      is_active: effectiveFilter,
      ...(q ? { q } : {}),
    }),
    listTrades(),
  ])

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Vendors
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Brenk&apos;s sub-vendors. These do not propagate to
            ServiceChannel — they live in our database only.{' '}
            {vendors.total} {effectiveFilter ? 'active' : 'inactive'}
            {q ? <> · matching <strong>“{q}”</strong></> : null}.
          </p>
        </div>
        <ActiveFilter current={is_active} />
      </header>

      <VendorsTableWithActions vendors={vendors.items} trades={trades} />
    </div>
  )
}

function ActiveFilter({ current }: { current: boolean | undefined }) {
  // Default state: no query param means "active". Treat undefined as
  // active so the toggle visually matches what the page shows.
  const showingInactive = current === false
  return (
    <div className="inline-flex rounded-md ring-1 ring-gray-300 dark:ring-white/10">
      <FilterLink href="/vendors?is_active=true" active={!showingInactive}>
        Active
      </FilterLink>
      <FilterLink href="/vendors?is_active=false" active={showingInactive}>
        Inactive
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
  // Plain anchor — full re-render refetches the list, which is what we
  // want when toggling filter. No JS needed.
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
