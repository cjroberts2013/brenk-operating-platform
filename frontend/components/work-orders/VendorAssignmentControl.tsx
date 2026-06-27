'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { PlusIcon, XMarkIcon } from '@heroicons/react/20/solid'

import {
  addAssignmentAction,
  removeAssignmentAction,
} from '@/app/(app)/work-orders/actions'
import type { AssignedVendor, VendorSummary } from '@/lib/api/types'

/**
 * Multi-vendor assignment control. Shows the assigned sub-vendors as chips
 * (each removable) plus an "Add vendor" picker, so a job can be split across
 * several vendors. The first chip is the "primary" the single-vendor readers
 * still key off.
 */
export function VendorAssignmentControl({
  workOrderId,
  assignments,
  activeVendors,
}: {
  workOrderId: number
  assignments: AssignedVendor[]
  activeVendors: VendorSummary[]
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const assignedIds = new Set(assignments.map((a) => a.vendor.id))
  const available = activeVendors.filter((v) => !assignedIds.has(v.id))

  function run(fn: () => Promise<{ error?: string }>) {
    setError(null)
    startTransition(async () => {
      const res = await fn()
      if (res.error) setError(res.error)
      else router.refresh()
    })
  }

  return (
    <div className="space-y-2">
      {assignments.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {assignments.map((a) => (
            <li
              key={a.vendor.id}
              className="inline-flex items-center gap-1 rounded-full bg-gray-100 py-0.5 pl-2.5 pr-1 text-xs dark:bg-white/10"
            >
              <Link
                href={`/vendors/${a.vendor.id}`}
                className="font-medium text-gray-800 hover:text-indigo-600 dark:text-gray-100 dark:hover:text-indigo-300"
              >
                {a.vendor.name}
              </Link>
              {a.job_type ? (
                <span className="text-gray-400">· {a.job_type.name}</span>
              ) : null}
              <button
                type="button"
                onClick={() => run(() => removeAssignmentAction(workOrderId, a.vendor.id))}
                disabled={pending}
                title={`Remove ${a.vendor.name}`}
                className="rounded-full p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-700 disabled:opacity-50 dark:hover:bg-white/10 dark:hover:text-gray-200"
              >
                <span className="sr-only">Remove</span>
                <XMarkIcon className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <span className="text-sm italic text-gray-500 dark:text-gray-400">
          Unassigned
        </span>
      )}

      {adding ? (
        <div className="flex items-center gap-2">
          <select
            defaultValue=""
            disabled={pending}
            onChange={(e) => {
              const id = Number(e.target.value)
              if (id > 0) {
                run(() => addAssignmentAction(workOrderId, id))
                setAdding(false)
              }
            }}
            className="block w-full max-w-xs rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-60 dark:border-white/10 dark:bg-gray-800 dark:text-white"
          >
            <option value="" disabled>
              — Pick a vendor —
            </option>
            {available.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setAdding(false)}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          disabled={pending || available.length === 0}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 dark:text-indigo-400 dark:hover:bg-indigo-500/10"
        >
          <PlusIcon className="size-3.5" />
          {assignments.length === 0 ? 'Assign vendor' : 'Add vendor'}
        </button>
      )}

      {error ? (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  )
}
