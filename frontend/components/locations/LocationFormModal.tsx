'use client'

import { useActionState, useEffect, useRef } from 'react'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import { XMarkIcon } from '@heroicons/react/24/outline'

import {
  updateLocationAction,
  type LocationActionState,
} from '@/app/(app)/locations/actions'
import type { LocationDetail } from '@/lib/api/types'

const INITIAL_STATE: LocationActionState = { error: null, attempt: 0 }

const RATING_OPTIONS = [
  { value: '', label: '— Unrated —' },
  { value: 'good', label: 'Good' },
  { value: 'watch', label: 'Watch' },
  { value: 'problem', label: 'Problem' },
]

export type LocationFormModalProps = {
  open: boolean
  onClose: () => void
  location: LocationDetail
}

export function LocationFormModal({
  open,
  onClose,
  location,
}: LocationFormModalProps) {
  const [state, formAction, pending] = useActionState<
    LocationActionState,
    FormData
  >(updateLocationAction, INITIAL_STATE)

  // Close on a fresh successful submit (not on initial mount).
  const lastObservedAttempt = useRef(0)
  useEffect(() => {
    if (
      state.attempt > lastObservedAttempt.current &&
      state.error === null &&
      !pending
    ) {
      lastObservedAttempt.current = state.attempt
      onClose()
    }
  }, [state.attempt, state.error, pending, onClose])

  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-gray-900/70 transition-opacity duration-200 data-closed:opacity-0"
      />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel
          transition
          className="relative w-full max-w-xl rounded-lg bg-white shadow-xl ring-1 ring-black/5 transition duration-200 data-closed:translate-y-2 data-closed:opacity-0 dark:bg-gray-900 dark:ring-white/10"
        >
          <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-white/10">
            <DialogTitle className="text-base font-semibold text-gray-900 dark:text-white">
              Edit location details
            </DialogTitle>
            <button
              type="button"
              onClick={onClose}
              className="-m-2 rounded-md p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <span className="sr-only">Close</span>
              <XMarkIcon className="size-5" />
            </button>
          </div>

          <form action={formAction} className="space-y-4 px-6 py-5">
            <input type="hidden" name="id" value={location.id} />

            <Field label="Rating">
              <select
                name="rating"
                defaultValue={location.rating ?? ''}
                className={inputClass}
              >
                {RATING_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="District manager">
              <input
                type="text"
                name="district_manager_name"
                placeholder="Name"
                defaultValue={location.district_manager_name ?? ''}
                className={inputClass}
              />
            </Field>

            <Row>
              <Field label="Manager phone">
                <input
                  type="tel"
                  name="district_manager_phone"
                  defaultValue={location.district_manager_phone ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Manager email">
                <input
                  type="email"
                  name="district_manager_email"
                  defaultValue={location.district_manager_email ?? ''}
                  className={inputClass}
                />
              </Field>
            </Row>

            <Field label="Notes / context">
              <textarea
                name="description"
                rows={4}
                placeholder="Running context — access quirks, recurring issues, who to call first…"
                defaultValue={location.description ?? ''}
                className={inputClass}
              />
            </Field>

            {state.error ? (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
                {state.error}
              </p>
            ) : null}

            <div className="flex items-center justify-end gap-3 border-t border-gray-200 pt-4 dark:border-white/10">
              <button
                type="button"
                onClick={onClose}
                disabled={pending}
                className="rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={pending}
                className="rounded-md bg-indigo-500 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
              >
                {pending ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        </DialogPanel>
      </div>
    </Dialog>
  )
}

const inputClass =
  'block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500'

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
        {label}
      </label>
      {children}
    </div>
  )
}
