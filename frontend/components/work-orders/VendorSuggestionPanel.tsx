'use client'

import type { ReactNode } from 'react'
import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { CheckIcon, SparklesIcon } from '@heroicons/react/20/solid'

import { quickAssignVendorAction } from '@/app/(app)/work-orders/actions'
import type { VendorSuggestion, VendorSuggestionResponse } from '@/lib/api/types'

/**
 * Assign-step helper: leads with the best-matching sub-vendor (trade +
 * service area + workload) and a one-click assign, plus a couple of
 * runner-ups. The manual dropdown is always rendered below so Daryl keeps
 * full control. Degrades to the dropdown alone when nothing strongly
 * matches or the suggestion fetch failed.
 */
export function VendorSuggestionPanel({
  workOrderId,
  suggestions,
  dropdown,
}: {
  workOrderId: number
  suggestions: VendorSuggestionResponse | null
  /** The manual VendorAssignmentControl, always shown beneath the panel. */
  dropdown: ReactNode
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [assigningId, setAssigningId] = useState<number | null>(null)

  function assign(vendorId: number) {
    setError(null)
    setAssigningId(vendorId)
    startTransition(async () => {
      const res = await quickAssignVendorAction(workOrderId, vendorId)
      if (res.error) {
        setError(res.error)
        setAssigningId(null)
      } else {
        router.refresh()
      }
    })
  }

  const top = suggestions?.top_pick ?? null
  const runnersUp = (suggestions?.ranked ?? [])
    .filter((s) => !s.is_current && s.vendor.id !== top?.vendor.id)
    .slice(0, 2)

  return (
    <div className="space-y-3">
      {top ? (
        <div className="rounded-md bg-white p-3 ring-1 ring-indigo-200 dark:bg-white/5 dark:ring-indigo-500/30">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
            <SparklesIcon className="size-3.5" />
            Suggested vendor
          </div>
          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <Link
                href={`/vendors/${top.vendor.id}`}
                className="font-medium text-gray-900 hover:text-indigo-600 dark:text-white dark:hover:text-indigo-300"
              >
                {top.vendor.name}
              </Link>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {top.reason}
              </p>
            </div>
            <button
              type="button"
              onClick={() => assign(top.vendor.id)}
              disabled={pending}
              className="inline-flex shrink-0 items-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              <CheckIcon className="size-4" />
              {assigningId === top.vendor.id && pending
                ? 'Assigning…'
                : `Assign ${firstName(top.vendor.name)}`}
            </button>
          </div>

          {runnersUp.length > 0 ? (
            <ul className="mt-3 space-y-1.5 border-t border-gray-100 pt-2 dark:border-white/10">
              {runnersUp.map((s) => (
                <RunnerUp
                  key={s.vendor.id}
                  suggestion={s}
                  pending={pending}
                  assigning={assigningId === s.vendor.id && pending}
                  onAssign={() => assign(s.vendor.id)}
                />
              ))}
            </ul>
          ) : null}
        </div>
      ) : suggestions ? (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {!suggestions.has_trade
            ? 'This work order has no trade set — pick a vendor below.'
            : suggestions.ranked.length === 0
              ? 'No active vendor is tagged for this trade yet — pick one below (or add the trade on their vendor page).'
              : 'No strong match nearby — pick a vendor below.'}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      ) : null}

      <div>
        {top ? (
          <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
            Or pick another:
          </p>
        ) : null}
        {dropdown}
      </div>
    </div>
  )
}

function RunnerUp({
  suggestion,
  pending,
  assigning,
  onAssign,
}: {
  suggestion: VendorSuggestion
  pending: boolean
  assigning: boolean
  onAssign: () => void
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <div className="min-w-0">
        <Link
          href={`/vendors/${suggestion.vendor.id}`}
          className="font-medium text-gray-700 hover:text-indigo-600 dark:text-gray-200 dark:hover:text-indigo-300"
        >
          {suggestion.vendor.name}
        </Link>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {suggestion.reason}
        </p>
      </div>
      <button
        type="button"
        onClick={onAssign}
        disabled={pending}
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200 hover:bg-indigo-50 disabled:opacity-60 dark:text-indigo-300 dark:ring-indigo-500/30 dark:hover:bg-indigo-500/10"
      >
        {assigning ? 'Assigning…' : 'Assign'}
      </button>
    </li>
  )
}

/** "Charles Roberts" → "Charles" for a compact button label. */
function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name
}
