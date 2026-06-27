'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import { CheckCircleIcon } from '@heroicons/react/20/solid'

import { setPaidAction } from '@/app/(app)/work-orders/[id]/markup-actions'
import { relativeTime } from '@/lib/format'

/**
 * Standalone "client paid Brenk" milestone. Surfaces in the next-step hero
 * only once a WO is invoiced — the last step in the pipeline — instead of
 * being buried in the markup helper, a pricing tool Daryl uses much earlier.
 */
export function MarkPaidControl({
  workOrderId,
  paidAt,
}: {
  workOrderId: number
  paidAt: string | null
}) {
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const isPaid = Boolean(paidAt)

  const toggle = (mark: boolean) => {
    setError(null)
    startTransition(async () => {
      const res = await setPaidAction(workOrderId, mark)
      if (res.error) setError(res.error)
    })
  }

  if (isPaid) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400">
          <CheckCircleIcon className="size-4" />
          Marked paid {relativeTime(paidAt)}
        </div>
        <button
          type="button"
          onClick={() => toggle(false)}
          disabled={pending}
          className="text-xs text-gray-500 underline hover:text-gray-700 disabled:opacity-60 dark:text-gray-400 dark:hover:text-gray-200"
        >
          {pending ? 'Saving…' : 'Undo (clear paid date)'}
        </button>
        {error ? (
          <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => toggle(true)}
        disabled={pending}
        className="w-full rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60 sm:w-auto"
      >
        {pending ? 'Saving…' : 'Mark paid'}
      </button>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Use this once the client has paid Brenk. When ServiceChannel marks the
        invoice paid, this is set automatically — it also shows on the{' '}
        <Link
          href="/invoices"
          className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
        >
          Invoices
        </Link>{' '}
        page.
      </p>
      {error ? (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  )
}
