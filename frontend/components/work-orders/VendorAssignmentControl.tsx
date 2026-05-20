'use client'

import { useActionState, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { PencilSquareIcon } from '@heroicons/react/20/solid'

import {
  assignVendorAction,
  type AssignVendorState,
} from '@/app/(app)/work-orders/actions'
import type { VendorRef, VendorSummary } from '@/lib/api/types'

const INITIAL_STATE: AssignVendorState = { error: null, attempt: 0 }

export function VendorAssignmentControl({
  workOrderId,
  currentVendor,
  activeVendors,
}: {
  workOrderId: number
  currentVendor: VendorRef | null
  activeVendors: VendorSummary[]
}) {
  const [editing, setEditing] = useState(false)
  const [state, formAction, pending] = useActionState<AssignVendorState, FormData>(
    assignVendorAction,
    INITIAL_STATE,
  )

  // Auto-flip out of edit mode when an attempt succeeds (error === null).
  // Same ref-based "new attempt only" trick we use in the vendor modal so
  // the initial mount with attempt=0 doesn't auto-collapse.
  const lastObservedAttempt = useRef(0)
  useEffect(() => {
    if (
      state.attempt > lastObservedAttempt.current &&
      state.error === null &&
      !pending
    ) {
      lastObservedAttempt.current = state.attempt
      setEditing(false)
    }
  }, [state.attempt, state.error, pending])

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        {currentVendor ? (
          <Link
            href={`/vendors/${currentVendor.id}`}
            className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
          >
            {currentVendor.name}
          </Link>
        ) : (
          <span className="italic text-gray-500 dark:text-gray-400">
            Unassigned
          </span>
        )}
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-200"
        >
          <PencilSquareIcon className="size-3" />
          {currentVendor ? 'Change' : 'Assign'}
        </button>
      </div>
    )
  }

  return (
    <form action={formAction} className="space-y-2">
      <input type="hidden" name="work_order_id" value={workOrderId} />
      <select
        name="assigned_vendor_id"
        defaultValue={currentVendor?.id ?? ''}
        disabled={pending}
        className="block w-full max-w-xs rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-60 dark:border-white/10 dark:bg-gray-800 dark:text-white"
      >
        <option value="">— Unassigned —</option>
        {activeVendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>
      {state.error ? (
        <p className="text-xs text-red-600 dark:text-red-400">{state.error}</p>
      ) : null}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-indigo-500 px-2 py-1 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
        >
          {pending ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          disabled={pending}
          className="rounded-md px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
