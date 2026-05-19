/**
 * Small display-formatting helpers used across the dashboard.
 * Locale-aware where it matters; otherwise minimal and explicit.
 */

const RELATIVE = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "2 days ago", "in 3 hours", "just now" */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const diffMs = then - Date.now()
  const absMs = Math.abs(diffMs)
  const MIN = 60_000
  const HOUR = 60 * MIN
  const DAY = 24 * HOUR
  if (absMs < MIN) return 'just now'
  if (absMs < HOUR) return RELATIVE.format(Math.round(diffMs / MIN), 'minute')
  if (absMs < DAY) return RELATIVE.format(Math.round(diffMs / HOUR), 'hour')
  return RELATIVE.format(Math.round(diffMs / DAY), 'day')
}

/** "May 13, 2026" — short month + day + year. */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/** "$750.00" — USD by default, falls back to "—" on null. */
export function money(
  amount: string | number | null | undefined,
  currency = 'USD',
): string {
  if (amount === null || amount === undefined || amount === '') return '—'
  const n = typeof amount === 'string' ? Number(amount) : amount
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  })
}
