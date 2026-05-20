'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowPathIcon } from '@heroicons/react/20/solid'

import { syncVendorsAction } from '@/app/(app)/vendors/actions'

type Result =
  | { kind: 'success'; created: number; updated: number; fetched: number; errors: number }
  | { kind: 'error'; message: string }

export function SyncFromScButton() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [result, setResult] = useState<Result | null>(null)

  function onClick() {
    setResult(null)
    startTransition(async () => {
      const r = await syncVendorsAction()
      if (r.error || !r.summary) {
        setResult({ kind: 'error', message: r.error ?? 'unknown error' })
        return
      }
      setResult({
        kind: 'success',
        fetched: r.summary.fetched,
        created: r.summary.created,
        updated: r.summary.updated,
        errors: r.summary.errors,
      })
      router.refresh()
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        className="inline-flex items-center gap-1 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-700 shadow-xs ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-60 dark:bg-gray-800 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-gray-700"
      >
        <ArrowPathIcon
          className={`size-4 ${pending ? 'animate-spin' : ''}`}
        />
        {pending ? 'Syncing…' : 'Sync from ServiceChannel'}
      </button>
      {result?.kind === 'success' ? (
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {result.fetched} fetched · {result.created} new ·{' '}
          {result.updated} updated
          {result.errors > 0 ? ` · ${result.errors} errors` : ''}
        </span>
      ) : null}
      {result?.kind === 'error' ? (
        <span className="text-xs text-red-600 dark:text-red-400">
          Sync failed: {result.message}
        </span>
      ) : null}
    </div>
  )
}
