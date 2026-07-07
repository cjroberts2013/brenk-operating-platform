'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckIcon, KeyIcon, XMarkIcon } from '@heroicons/react/20/solid'

import { accessFlagAction } from '@/app/(app)/work-orders/actions'
import type { WorkOrderDetail } from '@/lib/api/types'

/**
 * "Customer-unit access" banner. Shown when the backend's phrase scan
 * flagged the description or a store note as needing tenant coordination
 * (call ahead; tenant present with a key). The snippet is the receipt —
 * the exact text that tripped the flag. Actions: "Scheduled with tenant"
 * (records the call-ahead happened) and Dismiss (false positive; a new
 * matching store note re-opens it automatically).
 */
export function AccessFlagBanner({ wo }: { wo: WorkOrderDetail }) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const active = !!wo.brenk_access_flag_at && !wo.brenk_access_flag_dismissed_at
  if (!active) return null

  const scheduled = !!wo.brenk_access_scheduled_at

  function run(action: 'dismiss' | 'scheduled' | 'reopen') {
    setError(null)
    startTransition(async () => {
      const res = await accessFlagAction(wo.id, action)
      if (res.error) setError(res.error)
      else router.refresh()
    })
  }

  const sourceLabel =
    wo.brenk_access_flag_source === 'note' ? 'a store note' : 'the description'

  return (
    <section
      className={
        'rounded-lg px-4 py-3 ring-1 ' +
        (scheduled
          ? 'bg-green-50 ring-green-200 dark:bg-green-950/30 dark:ring-green-500/30'
          : 'bg-amber-50 ring-amber-300 dark:bg-amber-950/30 dark:ring-amber-500/40')
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <KeyIcon
            className={
              'mt-0.5 size-5 shrink-0 ' +
              (scheduled
                ? 'text-green-600 dark:text-green-400'
                : 'text-amber-600 dark:text-amber-400')
            }
          />
          <div>
            <p
              className={
                'text-sm font-semibold ' +
                (scheduled
                  ? 'text-green-900 dark:text-green-200'
                  : 'text-amber-900 dark:text-amber-200')
              }
            >
              {scheduled
                ? 'Customer-unit access — time scheduled with the tenant'
                : 'Customer-unit access — call ahead before sending anyone'}
            </p>
            <p className="mt-0.5 text-xs text-gray-600 dark:text-gray-300">
              {scheduled
                ? 'Marked scheduled'
                : 'The tenant likely needs to be there with a key'}
              {' · flagged from '}
              {sourceLabel}
            </p>
            {wo.brenk_access_flag_snippet ? (
              <p className="mt-1.5 rounded bg-white/60 px-2 py-1 font-mono text-xs text-gray-700 dark:bg-black/20 dark:text-gray-300">
                &ldquo;{wo.brenk_access_flag_snippet}&rdquo;
              </p>
            ) : null}
            {error ? (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {scheduled ? (
            <button
              type="button"
              onClick={() => run('reopen')}
              disabled={pending}
              className="rounded-md px-2.5 py-1.5 text-xs font-medium text-green-800 hover:bg-green-100 disabled:opacity-50 dark:text-green-300 dark:hover:bg-green-500/10"
            >
              Undo
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={() => run('scheduled')}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 disabled:opacity-50"
              >
                <CheckIcon className="size-3.5" />
                Scheduled with tenant
              </button>
              <button
                type="button"
                onClick={() => run('dismiss')}
                disabled={pending}
                title="Not applicable — dismiss (a new store note can re-flag it)"
                className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:text-amber-300 dark:hover:bg-amber-500/10"
              >
                <XMarkIcon className="size-3.5" />
                Dismiss
              </button>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
