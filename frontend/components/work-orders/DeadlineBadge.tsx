/**
 * Deadline badge — small pill flagging a WO's turnaround urgency.
 *
 * CubeSmart expects a 3-5 day turnaround; the backend computes the
 * deadline (scheduled_date, else call_date + 5d) and its urgency, and
 * this component just renders what it's given — no re-derivation
 * (single source of truth is `app/services/deadlines.py`).
 *
 *   overdue  → red   "Overdue 12d"
 *   due_soon → amber "Due in 2d" / "Due today"
 *   ok/null  → renders nothing (no clutter inside turnaround)
 */

import type { ReactNode } from 'react'
import { ClockIcon } from '@heroicons/react/20/solid'

import type { DeadlineUrgency } from '@/lib/api/types'

/** Mirrors the backend digest's due_label() buckets. */
function label(daysPast: number): string {
  if (daysPast >= 1) return `Overdue ${Math.floor(daysPast)}d`
  if (daysPast > -1) return 'Due today'
  return `Due in ${Math.ceil(-daysPast)}d`
}

export function DeadlineBadge({
  urgency,
  daysPast,
}: {
  urgency: DeadlineUrgency | null
  daysPast: number | null
}): ReactNode {
  if (daysPast === null || (urgency !== 'overdue' && urgency !== 'due_soon')) {
    return null
  }
  const classes =
    urgency === 'overdue'
      ? 'bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400'
      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400'
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-sm px-1.5 py-px text-[10px] font-medium uppercase ${classes}`}
      title="CubeSmart turnaround deadline (scheduled date)"
    >
      <ClockIcon className="size-2.5" />
      {label(daysPast)}
    </span>
  )
}
