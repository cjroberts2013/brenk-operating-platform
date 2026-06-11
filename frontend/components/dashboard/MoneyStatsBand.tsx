import Link from 'next/link'

import type { MoneyStats } from '@/lib/api/types'
import { money } from '@/lib/format'

/**
 * Three dollar stats above the pipeline funnel — the questions counts
 * can't answer: how much completed work hasn't been billed, how much
 * is invoiced but unpaid, and what actually got paid this month.
 *
 * Each tile links into the Invoices page, where the rows behind the
 * number live.
 */
export function MoneyStatsBand({ stats }: { stats: MoneyStats }) {
  const hasPriced = stats.unbilled_priced_count > 0
  const hasUnpriced = stats.unbilled_unpriced_count > 0

  // Unbilled headline: exact total when priced work exists; otherwise
  // the NTE ceiling, labeled as such, so the number is never silently
  // a mix of exact and estimated.
  const unbilledValue = hasPriced
    ? money(stats.unbilled_priced_total)
    : hasUnpriced
      ? `up to ${money(stats.unbilled_unpriced_nte_total)}`
      : money('0')
  const unbilledDetail = hasPriced
    ? hasUnpriced
      ? `${stats.unbilled_priced_count} priced · ${stats.unbilled_unpriced_count} unpriced (up to ${money(stats.unbilled_unpriced_nte_total)} more by NTE)`
      : `${stats.unbilled_priced_count} work order${stats.unbilled_priced_count === 1 ? '' : 's'} priced and ready`
    : hasUnpriced
      ? `${stats.unbilled_unpriced_count} work order${stats.unbilled_unpriced_count === 1 ? '' : 's'} not yet priced — NTE ceiling`
      : 'Nothing waiting to be billed'

  const awaitingDetail =
    stats.awaiting_count === 0
      ? 'No open SC invoices synced yet'
      : `${stats.awaiting_count} invoice${stats.awaiting_count === 1 ? '' : 's'} in ServiceChannel` +
        (stats.awaiting_unknown_count > 0
          ? ` · ${stats.awaiting_unknown_count} without an amount`
          : '')

  const paidDetail =
    stats.paid_month_count === 0
      ? 'Nothing paid yet this month'
      : `${stats.paid_month_count} work order${stats.paid_month_count === 1 ? '' : 's'}`

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <MoneyTile
        label="Unbilled work"
        value={unbilledValue}
        detail={unbilledDetail}
        href="/invoices"
        attention={hasPriced || hasUnpriced}
      />
      <MoneyTile
        label="Awaiting payment"
        value={money(stats.awaiting_total)}
        detail={awaitingDetail}
        href="/invoices"
      />
      <MoneyTile
        label={`Paid in ${stats.month_label}`}
        value={money(stats.paid_month_total)}
        detail={paidDetail}
        extra={
          stats.paid_month_profit !== null ? (
            <span className="font-medium text-emerald-700 dark:text-emerald-400">
              {money(stats.paid_month_profit)} profit
            </span>
          ) : null
        }
        href="/invoices"
      />
    </div>
  )
}

function MoneyTile({
  label,
  value,
  detail,
  extra,
  href,
  attention = false,
}: {
  label: string
  value: string
  detail: string
  extra?: React.ReactNode
  href: string
  /** Amber accent when the number represents money waiting on Brenk. */
  attention?: boolean
}) {
  return (
    <Link
      href={href}
      className="group block rounded-lg bg-white p-4 ring-1 ring-gray-200 transition hover:ring-gray-300 dark:bg-gray-900 dark:ring-white/10 dark:hover:ring-white/20"
    >
      <p className="text-xs font-medium tracking-wide text-gray-600 uppercase dark:text-gray-400">
        {label}
      </p>
      <p
        className={`mt-2 text-2xl font-semibold ${
          attention
            ? 'text-amber-700 dark:text-amber-400'
            : 'text-gray-900 dark:text-white'
        }`}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
        {detail}
        {extra ? <> · {extra}</> : null}
      </p>
    </Link>
  )
}
