import Link from 'next/link'

import { getReportsSummary } from '@/lib/api/reports'
import type { MarkupByTrade } from '@/lib/api/types'

function usd(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
  })
}

function pct(value: number | null): string {
  return value === null ? '—' : `${value}%`
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="rounded-lg bg-white p-4 ring-1 ring-gray-200 dark:bg-gray-900 dark:ring-white/10">
      <p className="text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
        {value}
      </p>
      {sub ? (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{sub}</p>
      ) : null}
    </div>
  )
}

// Color the actual-vs-default delta: near-zero is fine (gray), a real
// gap means the configured default isn't matching Daryl's choices.
function deltaClass(delta: number | null): string {
  if (delta === null) return 'text-gray-400 dark:text-gray-500'
  if (Math.abs(delta) < 5) return 'text-gray-600 dark:text-gray-300'
  return delta > 0
    ? 'text-emerald-700 dark:text-emerald-400'
    : 'text-amber-700 dark:text-amber-400'
}

function formatDelta(row: MarkupByTrade): string {
  if (row.delta_percent === null) {
    return row.default_markup_percent === null ? 'no default' : '—'
  }
  const sign = row.delta_percent > 0 ? '+' : ''
  return `${sign}${row.delta_percent} pts`
}

export default async function ReportsPage() {
  const data = await getReportsSummary()
  const { totals, markup_by_trade, vendor_spend } = data
  const hasData = totals.jobs_with_markup > 0

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Reports
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Margin and spend across work orders you&apos;ve marked up. Figures
          are Brenk-confidential — they&apos;re never sent to ServiceChannel.
        </p>
      </header>

      {!hasData ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center dark:border-white/10">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
            No markup data yet.
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500 dark:text-gray-400">
            These reports fill in as you use the markup helper on the{' '}
            <Link
              href="/invoices"
              className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            >
              invoice queue
            </Link>
            . Once a work order has a vendor cost and a markup %, it shows up
            here — spend by vendor, and how your actual markup compares to the
            per-trade defaults set in{' '}
            <Link
              href="/settings"
              className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Settings
            </Link>
            .
          </p>
        </div>
      ) : (
        <>
          {/* ---- top-line money ---- */}
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Marked-up jobs"
              value={String(totals.jobs_with_markup)}
            />
            <StatCard
              label="Total billed"
              value={usd(totals.total_billed)}
              sub="vendor cost + margin"
            />
            <StatCard
              label="Vendor cost"
              value={usd(totals.total_vendor_cost)}
              sub="what Brenk paid subs"
            />
            <StatCard
              label="Margin"
              value={usd(totals.total_margin)}
              sub={
                totals.blended_markup_percent !== null
                  ? `${totals.blended_markup_percent}% blended markup`
                  : undefined
              }
            />
          </section>

          {/* ---- markup actual vs. default, by trade ---- */}
          <section className="space-y-3">
            <div>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Markup by trade — actual vs. default
              </h2>
              <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
                Compares the markup you actually chose against the per-trade
                default. A large gap means the default in Settings probably
                needs adjusting — or markup is really driven by something other
                than trade.
              </p>
            </div>
            <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
                <thead className="bg-gray-50 dark:bg-gray-800/40">
                  <tr>
                    <Th>Trade</Th>
                    <Th className="text-right">Jobs</Th>
                    <Th className="text-right">Default</Th>
                    <Th className="text-right">Avg actual</Th>
                    <Th className="text-right">Delta</Th>
                    <Th className="text-right">Vendor cost</Th>
                    <Th className="text-right">Margin</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white dark:divide-white/5 dark:bg-gray-900">
                  {markup_by_trade.map((row) => (
                    <tr key={row.trade_id}>
                      <Td className="font-medium text-gray-900 dark:text-white">
                        {row.trade_name}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {row.jobs_with_markup}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {pct(row.default_markup_percent)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {pct(row.avg_actual_markup_percent)}
                      </Td>
                      <Td
                        className={`text-right tabular-nums ${deltaClass(row.delta_percent)}`}
                      >
                        {formatDelta(row)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {usd(row.total_vendor_cost)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {usd(row.total_margin)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ---- vendor spend ---- */}
          <section className="space-y-3">
            <div>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Spend by vendor
              </h2>
              <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
                What you&apos;ve paid each sub-vendor across marked-up jobs, and
                the margin earned on top.
              </p>
            </div>
            <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
                <thead className="bg-gray-50 dark:bg-gray-800/40">
                  <tr>
                    <Th>Vendor</Th>
                    <Th className="text-right">Jobs</Th>
                    <Th className="text-right">Vendor cost</Th>
                    <Th className="text-right">Margin</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white dark:divide-white/5 dark:bg-gray-900">
                  {vendor_spend.map((row) => (
                    <tr key={row.vendor_id}>
                      <Td className="font-medium text-gray-900 dark:text-white">
                        {row.vendor_name}
                      </Td>
                      <Td className="text-right tabular-nums">{row.jobs}</Td>
                      <Td className="text-right tabular-nums">
                        {usd(row.total_vendor_cost)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {usd(row.total_margin)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Th({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <th
      scope="col"
      className={`px-4 py-2.5 text-left text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400 ${className}`}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <td className={`px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 ${className}`}>
      {children}
    </td>
  )
}
