'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircleIcon } from '@heroicons/react/20/solid'

import { setAssignmentNotifiedAction } from '@/app/(app)/work-orders/actions'
import type { AssignedVendor } from '@/lib/api/types'
import { relativeTime } from '@/lib/format'

/**
 * Per-vendor "notified" milestone. Each assigned sub-vendor gets its own
 * mark-notified toggle, so a split job tracks who's actually been reached.
 */
export function VendorNotifiedControl({
  workOrderId,
  assignments,
}: {
  workOrderId: number
  assignments: AssignedVendor[]
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  function toggle(vendorId: number, mark: boolean) {
    setError(null)
    startTransition(async () => {
      const res = await setAssignmentNotifiedAction(workOrderId, vendorId, mark)
      if (res.error) setError(res.error)
      else router.refresh()
    })
  }

  if (assignments.length === 0) {
    return (
      <span className="text-xs text-gray-400 dark:text-gray-500">
        Assign a vendor first
      </span>
    )
  }

  return (
    <div className="space-y-1.5">
      {assignments.map((a) => (
        <div
          key={a.vendor.id}
          className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"
        >
          {a.notified_at ? (
            <>
              <span className="inline-flex items-center gap-1 text-gray-700 dark:text-gray-200">
                <CheckCircleIcon className="size-4 text-green-600 dark:text-green-400" />
                {a.vendor.name} · notified {relativeTime(a.notified_at)}
              </span>
              <button
                type="button"
                onClick={() => toggle(a.vendor.id, false)}
                disabled={pending}
                className="rounded-md px-1.5 py-0.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-60 dark:text-gray-400 dark:hover:bg-white/5"
              >
                Undo
              </button>
            </>
          ) : (
            <>
              <span className="text-gray-700 dark:text-gray-200">
                {a.vendor.name}
              </span>
              <button
                type="button"
                onClick={() => toggle(a.vendor.id, true)}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-2 py-0.5 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
              >
                Mark notified
              </button>
            </>
          )}
        </div>
      ))}
      {error ? (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  )
}
