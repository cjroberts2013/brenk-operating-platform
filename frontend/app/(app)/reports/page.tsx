import Link from 'next/link'

import { BarChart, type BarDatum } from '@/components/reports/BarChart'
import { PayablesSection } from '@/components/reports/PayablesSection'
import { getPayables, getReportsSummary } from '@/lib/api/reports'
import type { CategoryOverview, MarkupByTrade } from '@/lib/api/types'

function usd(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function usdShort(n: number): string {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}

function pct(value: number | null): string {
  return value === null ? '—' : `${value}%`
}

export default async function ReportsPage() {
  const [data, payables] = await Promise.all([getReportsSummary(), getPayables()])
  const {
    totals,
    markup_by_trade,
    markup_by_category,
    vendor_spend,
    category_overview,
    coverage,
  } = data

  const hasMarkup = totals.jobs_with_markup > 0
  const revenueBars: BarDatum[] = category_overview
    .filter((c) => Number(c.billed) > 0)
    .map((c) => ({
      label: c.category,
      value: Number(c.billed),
      valueLabel: usdShort(Number(c.billed)),
    }))
  const volumeBars: BarDatum[] = [...category_overview]
    .sort((a, b) => b.jobs - a.jobs)
    .map((c) => ({
      label: c.category,
      value: c.jobs,
      valueLabel: String(c.jobs),
    }))
  const marginBars: BarDatum[] = [...markup_by_category]
    .sort((a, b) => Number(b.total_margin) - Number(a.total_margin))
    .map((c) => ({
      label: c.category,
      value: Number(c.total_margin),
      valueLabel: usdShort(Number(c.total_margin)),
    }))

  const showNudge =
    coverage !== null &&
    coverage.invoiced_jobs > 0 &&
    coverage.priced_jobs < coverage.invoiced_jobs

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Reports
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Where the work and the money are, by job category. Markup figures
          are Brenk-confidential — never sent to ServiceChannel.
        </p>
      </header>

      {showNudge ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-500/30 dark:bg-amber-500/10">
          <p className="font-medium text-amber-900 dark:text-amber-200">
            Unlock profit analytics
          </p>
          <p className="mt-1 text-amber-800 dark:text-amber-300/90">
            {coverage!.priced_jobs} of {coverage!.invoiced_jobs} invoiced jobs
            have a cost + markup entered. Profit and margin-by-category fill in
            as you price jobs in the{' '}
            <Link
              href="/invoices"
              className="font-medium underline hover:no-underline"
            >
              markup helper
            </Link>
            .
          </p>
        </div>
      ) : null}

      {/* ====== SUB-VENDOR PAYABLES ====== */}
      <PayablesSection payables={payables} />

      {/* ====== CATEGORY OVERVIEW (populated now) ====== */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            By category
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
            Billed revenue comes from linked ServiceChannel invoices; job
            volume from every categorized work order.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartCard title="Billed revenue by category">
            <BarChart
              data={revenueBars}
              barClassName="bg-emerald-500"
              emptyLabel="No billed invoices linked to categories yet."
            />
          </ChartCard>
          <ChartCard title="Jobs by category">
            <BarChart data={volumeBars} barClassName="bg-indigo-500" />
          </ChartCard>
        </div>

        <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
            <thead className="bg-gray-50 dark:bg-gray-800/40">
              <tr>
                <Th>Category</Th>
                <Th className="text-right">Jobs</Th>
                <Th className="text-right">Invoiced</Th>
                <Th className="text-right">Billed</Th>
                <Th className="text-right">Paid</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white dark:divide-white/5 dark:bg-gray-900">
              {category_overview.map((row) => (
                <CategoryRow key={row.category} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ====== PROFIT & MARKUP (fills in) ====== */}
      <section className="space-y-4">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">
          Profit &amp; markup
        </h2>

        {!hasMarkup ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center dark:border-white/10">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Profit, margin, and markup analytics appear here once jobs are
              priced in the markup helper. None yet.
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard label="Marked-up jobs" value={String(totals.jobs_with_markup)} />
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
            </div>

            <ChartCard title="Margin by category">
              <BarChart data={marginBars} barClassName="bg-emerald-500" />
            </ChartCard>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Markup by trade — actual vs. default
              </h3>
              <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
                  <thead className="bg-gray-50 dark:bg-gray-800/40">
                    <tr>
                      <Th>Trade</Th>
                      <Th className="text-right">Jobs</Th>
                      <Th className="text-right">Default</Th>
                      <Th className="text-right">Avg actual</Th>
                      <Th className="text-right">Delta</Th>
                      <Th className="text-right">Margin</Th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white dark:divide-white/5 dark:bg-gray-900">
                    {markup_by_trade.map((row) => (
                      <tr key={row.trade_id}>
                        <Td className="font-medium text-gray-900 dark:text-white">
                          {row.trade_name}
                        </Td>
                        <Td className="text-right tabular-nums">{row.jobs_with_markup}</Td>
                        <Td className="text-right tabular-nums">
                          {pct(row.default_markup_percent)}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {pct(row.avg_actual_markup_percent)}
                        </Td>
                        <Td className={`text-right tabular-nums ${deltaClass(row.delta_percent)}`}>
                          {formatDelta(row)}
                        </Td>
                        <Td className="text-right tabular-nums">{usd(row.total_margin)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Spend by vendor
              </h3>
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
                        <Td className="text-right tabular-nums">{usd(row.total_margin)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

function CategoryRow({ row }: { row: CategoryOverview }) {
  const billed = Number(row.billed)
  return (
    <tr>
      <Td className="font-medium text-gray-900 dark:text-white">{row.category}</Td>
      <Td className="text-right tabular-nums">{row.jobs}</Td>
      <Td className="text-right tabular-nums">{row.invoiced_jobs}</Td>
      <Td className="text-right tabular-nums">
        {billed > 0 ? usd(row.billed) : '—'}
      </Td>
      <Td className="text-right tabular-nums">
        {Number(row.paid) > 0 ? usd(row.paid) : '—'}
      </Td>
    </tr>
  )
}

function ChartCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg p-4 ring-1 ring-gray-200 dark:ring-white/10">
      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
        {title}
      </h3>
      {children}
    </div>
  )
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
