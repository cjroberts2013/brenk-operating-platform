'use client'

import { useState, useTransition } from 'react'
import { CheckCircleIcon } from '@heroicons/react/20/solid'

import { setNotifiedAction } from '@/app/(app)/work-orders/[id]/markup-actions'
import { relativeTime } from '@/lib/format'

/**
 * Interactive "Vendor notified" milestone for the workflow checklist.
 * Marks when Daryl actually texted/called the assigned sub-vendor —
 * the "assigned in our heads but never told them" failure mode.
 */
export function VendorNotifiedControl({
  workOrderId,
  notifiedAt,
  hasVendor,
}: {
  workOrderId: number
  notifiedAt: string | null
  hasVendor: boolean
}) {
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const toggle = (mark: boolean) => {
    setError(null)
    startTransition(async () => {
      const res = await setNotifiedAction(workOrderId, mark)
      if (res.error) setError(res.error)
    })
  }

  if (notifiedAt) {
    return (
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span className="inline-flex items-center gap-1 text-gray-700 dark:text-gray-200">
          <CheckCircleIcon className="size-4 text-green-600 dark:text-green-400" />
          Notified {relativeTime(notifiedAt)}
        </span>
        <button
          type="button"
          onClick={() => toggle(false)}
          disabled={pending}
          className="rounded-md px-1.5 py-0.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-60 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-200"
        >
          {pending ? 'Saving…' : 'Undo'}
        </button>
        {error ? (
          <p className="w-full text-xs text-red-600 dark:text-red-400">{error}</p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <button
        type="button"
        onClick={() => toggle(true)}
        disabled={pending}
        className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-2 py-1 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
      >
        {pending ? 'Saving…' : 'Mark notified'}
      </button>
      {!hasVendor ? (
        <span className="text-xs text-gray-400 dark:text-gray-500">
          Assign a vendor first
        </span>
      ) : null}
      {error ? (
        <p className="w-full text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  )
}
