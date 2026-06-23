'use client'

import { useActionState, useEffect, useRef, useState } from 'react'
import { CheckIcon, PencilSquareIcon, SparklesIcon } from '@heroicons/react/20/solid'

import {
  setCategoryAction,
  type CategoryState,
} from '@/app/(app)/work-orders/actions'

const INITIAL_STATE: CategoryState = { error: null, attempt: 0 }

/**
 * Job-category card. Gemini sets a base category (source 'ai'); the operator
 * confirms it (→ 'confirmed') or changes it (→ 'manual'). Drives the
 * category-average markup suggestion and the profit-by-category report.
 */
export function CategoryControl({
  workOrderId,
  category,
  source,
  categories,
}: {
  workOrderId: number
  category: string | null
  source: string | null
  categories: string[]
}) {
  const [editing, setEditing] = useState(false)
  const [state, formAction, pending] = useActionState<CategoryState, FormData>(
    setCategoryAction,
    INITIAL_STATE,
  )

  // Collapse the editor when a save succeeds.
  const lastObserved = useRef(0)
  useEffect(() => {
    if (state.attempt > lastObserved.current && state.error === null && !pending) {
      lastObserved.current = state.attempt
      setEditing(false)
    }
  }, [state.attempt, state.error, pending])

  const unreviewed = source === 'ai'

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Job category
        </h2>
        {unreviewed ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
            <SparklesIcon className="size-3" />
            AI · confirm?
          </span>
        ) : null}
      </header>

      <div className="px-4 py-3 text-sm">
        {!editing ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900 dark:text-white">
                {category ?? (
                  <span className="italic text-gray-500">Uncategorized</span>
                )}
              </span>
              {source === 'confirmed' ? (
                <span className="inline-flex items-center gap-0.5 text-xs text-green-600 dark:text-green-400">
                  <CheckIcon className="size-3.5" />
                  confirmed
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {unreviewed && category ? (
                <form action={formAction}>
                  <input type="hidden" name="work_order_id" value={workOrderId} />
                  {/* No brenk_category field → the action treats it as confirm. */}
                  <button
                    type="submit"
                    disabled={pending}
                    className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
                  >
                    <CheckIcon className="size-3.5" />
                    Confirm
                  </button>
                </form>
              ) : null}
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-white/5"
              >
                <PencilSquareIcon className="size-3.5" />
                {category ? 'Change' : 'Set category'}
              </button>
            </div>
            {state.error ? (
              <p className="text-xs text-red-600 dark:text-red-400">{state.error}</p>
            ) : null}
          </div>
        ) : (
          <form action={formAction} className="space-y-2">
            <input type="hidden" name="work_order_id" value={workOrderId} />
            <select
              name="brenk_category"
              defaultValue={category ?? ''}
              disabled={pending}
              className="block w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
            >
              <option value="" disabled>
                — Select a category —
              </option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
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
                className="rounded-md bg-indigo-500 px-3 py-1 text-sm font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
              >
                {pending ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                disabled={pending}
                className="rounded-md px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  )
}
