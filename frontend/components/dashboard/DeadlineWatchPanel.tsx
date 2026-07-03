/**
 * Deadline watch — compact banner tracking CubeSmart's 3-5 day
 * turnaround expectation.
 *
 * Counts come from the backend's `deadline_watch` payload (same
 * definitions as the `?deadline=` list filter, so every count equals
 * the row total of the list it links to). Distinct from "Stuck":
 * stuck measures silence since the last SC update, deadline watch
 * measures the promise made to the client (scheduled date).
 */

import Link from 'next/link'
import { ClockIcon } from '@heroicons/react/24/outline'

import type { DeadlineWatch } from '@/lib/api/types'

export function DeadlineWatchPanel({ watch }: { watch: DeadlineWatch }) {
  const atRisk = watch.overdue_count + watch.due_soon_count

  if (atRisk === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 px-4 py-3 dark:border-white/10">
        <p className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <ClockIcon className="size-4" />
          Deadline watch: everything is inside its 3-5 day turnaround.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg bg-red-50/60 px-4 py-3 ring-1 ring-red-200 dark:bg-red-950/20 dark:ring-red-900">
      <span className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
        <ClockIcon className="size-4 text-red-600 dark:text-red-400" />
        Deadline watch
      </span>
      <span className="text-sm text-gray-700 dark:text-gray-300">
        {watch.overdue_count > 0 ? (
          <Link
            href="/work-orders?deadline=overdue"
            className="font-semibold text-red-700 hover:underline dark:text-red-400"
          >
            {watch.overdue_count} past deadline
          </Link>
        ) : (
          <span>0 past deadline</span>
        )}
        {' · '}
        {watch.due_soon_count > 0 ? (
          <Link
            href="/work-orders?deadline=due_soon"
            className="font-semibold text-amber-700 hover:underline dark:text-amber-400"
          >
            {watch.due_soon_count} due within {watch.due_soon_window_days} days
          </Link>
        ) : (
          <span>0 due within {watch.due_soon_window_days} days</span>
        )}
        {watch.waiting_on_cubesmart_count > 0 ? (
          <span className="text-gray-500 dark:text-gray-400">
            {' '}
            ({watch.waiting_on_cubesmart_count} of these waiting on CubeSmart)
          </span>
        ) : null}
      </span>
      <Link
        href="/work-orders?deadline=at_risk"
        className="ml-auto text-xs font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
      >
        View all at-risk
      </Link>
    </div>
  )
}
