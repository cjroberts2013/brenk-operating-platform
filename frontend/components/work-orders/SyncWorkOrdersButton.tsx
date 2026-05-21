'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowPathIcon } from '@heroicons/react/20/solid'

import { syncWorkOrdersAction } from '@/app/(app)/work-orders/actions'
import { relativeTime } from '@/lib/format'

type Result =
  | { kind: 'success'; fetched: number; upserted: number; notesSynced: number; errors: number }
  | { kind: 'error'; message: string }

export function SyncWorkOrdersButton({
  lastSyncedAt,
}: {
  /** ISO 8601 string from /api/v1/work-orders/sync-status, or null
   * on an empty database (no sync has ever run). */
  lastSyncedAt: string | null
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [result, setResult] = useState<Result | null>(null)

  function onClick() {
    setResult(null)
    startTransition(async () => {
      const r = await syncWorkOrdersAction()
      if (r.error || !r.summary) {
        setResult({ kind: 'error', message: r.error ?? 'unknown error' })
        return
      }
      setResult({
        kind: 'success',
        fetched: r.summary.fetched,
        upserted: r.summary.upserted,
        notesSynced: r.summary.notes_synced,
        errors: r.summary.errors,
      })
      // Server action already revalidated; refresh the route so the
      // header's last-synced line re-renders with the new MAX.
      router.refresh()
    })
  }

  // The header text is the live "last synced …" status. Right after a
  // successful run we replace it with the run summary; otherwise show
  // the persisted timestamp. ServiceChannel runs hourly in the
  // background — this is here for when Daryl wants a fresh pull right
  // now (eg. an email just came in).
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        className="inline-flex items-center gap-1 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-700 shadow-xs ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-60 dark:bg-gray-800 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-gray-700"
      >
        <ArrowPathIcon
          className={`size-4 ${pending ? 'animate-spin' : ''}`}
        />
        {pending ? 'Syncing…' : 'Sync now'}
      </button>
      <SyncStatusLine
        pending={pending}
        result={result}
        lastSyncedAt={lastSyncedAt}
      />
    </div>
  )
}

function SyncStatusLine({
  pending,
  result,
  lastSyncedAt,
}: {
  pending: boolean
  result: Result | null
  lastSyncedAt: string | null
}) {
  if (pending) {
    return (
      <span className="text-xs text-gray-500 dark:text-gray-400">
        Pulling latest from ServiceChannel…
      </span>
    )
  }
  if (result?.kind === 'error') {
    return (
      <span className="text-xs text-red-600 dark:text-red-400">
        Sync failed: {result.message}
      </span>
    )
  }
  if (result?.kind === 'success') {
    return (
      <span className="text-xs text-gray-500 dark:text-gray-400">
        Synced {result.fetched} work orders
        {result.notesSynced > 0
          ? ` · ${result.notesSynced} notes refreshed`
          : ''}
        {result.errors > 0 ? ` · ${result.errors} errors` : ''}
      </span>
    )
  }
  if (lastSyncedAt) {
    return (
      <span
        className="text-xs text-gray-500 dark:text-gray-400"
        title={lastSyncedAt}
      >
        Last synced {relativeTime(lastSyncedAt)}
        {' · '}auto-syncs every hour
      </span>
    )
  }
  return (
    <span className="text-xs text-gray-500 dark:text-gray-400">
      Never synced — click Sync now to populate.
    </span>
  )
}
