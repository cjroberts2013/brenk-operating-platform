'use client'

import { useActionState, useEffect, useRef } from 'react'
import { PlusIcon } from '@heroicons/react/20/solid'

import {
  addGateCodeAction,
  invalidateGateCodeAction,
  type LocationActionState,
} from '@/app/(app)/locations/actions'
import type { GateCode } from '@/lib/api/types'

const INITIAL_STATE: LocationActionState = { error: null, attempt: 0 }

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function GateCodesPanel({
  locationId,
  active,
  history,
}: {
  locationId: number
  active: GateCode[]
  history: GateCode[]
}) {
  const [state, formAction, pending] = useActionState<
    LocationActionState,
    FormData
  >(addGateCodeAction, INITIAL_STATE)

  // Clear the inputs after a successful add.
  const formRef = useRef<HTMLFormElement>(null)
  const lastObservedAttempt = useRef(0)
  useEffect(() => {
    if (
      state.attempt > lastObservedAttempt.current &&
      state.error === null &&
      !pending
    ) {
      lastObservedAttempt.current = state.attempt
      formRef.current?.reset()
    }
  }, [state.attempt, state.error, pending])

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Gate &amp; access codes
        </h2>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          When a code changes, invalidate the old one and add the new — the
          history is kept.
        </p>
      </header>

      <div className="space-y-4 px-4 py-4">
        {/* Active codes */}
        {active.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No active codes.
          </p>
        ) : (
          <ul className="space-y-2">
            {active.map((gc) => (
              <li
                key={gc.id}
                className="flex items-center justify-between gap-3 rounded-md bg-gray-50 px-3 py-2 dark:bg-white/5"
              >
                <div>
                  <span className="font-mono text-sm font-semibold text-gray-900 dark:text-white">
                    {gc.code}
                  </span>
                  {gc.label ? (
                    <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                      {gc.label}
                    </span>
                  ) : null}
                </div>
                <InvalidateForm locationId={locationId} code={gc} />
              </li>
            ))}
          </ul>
        )}

        {/* Add a code */}
        <form
          ref={formRef}
          action={formAction}
          className="flex flex-wrap items-end gap-2 border-t border-gray-200 pt-4 dark:border-white/10"
        >
          <input type="hidden" name="location_id" value={locationId} />
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
              Code
            </label>
            <input
              type="text"
              name="code"
              required
              placeholder="e.g. 1234#"
              className={inputClass}
            />
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
              Label (optional)
            </label>
            <input
              type="text"
              name="label"
              placeholder="e.g. front gate"
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            disabled={pending}
            className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
          >
            <PlusIcon className="size-4" />
            {pending ? 'Adding…' : 'Add code'}
          </button>
        </form>

        {state.error ? (
          <p className="text-xs text-red-600 dark:text-red-400">{state.error}</p>
        ) : null}

        {/* History */}
        {history.length > 0 ? (
          <details className="border-t border-gray-200 pt-3 dark:border-white/10">
            <summary className="cursor-pointer text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
              Previous codes ({history.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {history.map((gc) => (
                <li
                  key={gc.id}
                  className="flex items-center justify-between gap-3 text-sm text-gray-500 dark:text-gray-400"
                >
                  <span className="font-mono line-through">{gc.code}</span>
                  <span className="text-xs">
                    {gc.label ? `${gc.label} · ` : ''}retired{' '}
                    {formatDate(gc.invalidated_at)}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </section>
  )
}

function InvalidateForm({
  locationId,
  code,
}: {
  locationId: number
  code: GateCode
}) {
  function confirmInvalidate(event: React.FormEvent<HTMLFormElement>) {
    if (
      !window.confirm(
        `Invalidate code "${code.code}"? It moves to history and stays on record.`,
      )
    ) {
      event.preventDefault()
    }
  }
  return (
    <form action={invalidateGateCodeAction} onSubmit={confirmInvalidate}>
      <input type="hidden" name="location_id" value={locationId} />
      <input type="hidden" name="code_id" value={code.id} />
      <button
        type="submit"
        className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950"
      >
        Invalidate
      </button>
    </form>
  )
}

const inputClass =
  'block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500'
