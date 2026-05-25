'use client'

import { useState, useTransition } from 'react'
import { CheckIcon } from '@heroicons/react/20/solid'

import { setTradeMarkupAction } from '@/app/(app)/settings/markup-actions'
import type { TradeRef } from '@/lib/api/types'

export function MarkupDefaultsTable({ trades }: { trades: TradeRef[] }) {
  return (
    <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <th
                scope="col"
                className="px-3 py-2 text-left text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400"
              >
                Trade
              </th>
              <th
                scope="col"
                className="w-44 px-3 py-2 text-right text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400"
              >
                Default markup %
              </th>
              <th scope="col" className="w-10 px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {trades.map((trade) => (
              <MarkupRow key={trade.id} trade={trade} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MarkupRow({ trade }: { trade: TradeRef }) {
  const [value, setValue] = useState<string>(trade.default_markup_percent ?? '')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [savedTick, setSavedTick] = useState(0)

  // Only enable the Save button when the local value differs from
  // what's in the DB. Avoids accidentally re-posting unchanged
  // numbers and keeps the green-check feedback meaningful.
  const dbValue = trade.default_markup_percent ?? ''
  const dirty = value.trim() !== dbValue

  function save() {
    setError(null)
    startTransition(async () => {
      const result = await setTradeMarkupAction(trade.id, value)
      if (result.error) setError(result.error)
      else setSavedTick((n) => n + 1)
    })
  }

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td className="px-3 py-2 align-middle">
        <span className="text-gray-900 dark:text-white">{trade.name}</span>
        {trade.sc_trade_id === null ? (
          <span className="ml-2 rounded-sm bg-indigo-50 px-1.5 py-px text-[10px] font-medium text-indigo-700 uppercase dark:bg-indigo-950/40 dark:text-indigo-300">
            Brenk
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2 text-right align-middle">
        <div className="flex items-center justify-end gap-1">
          <input
            type="number"
            inputMode="decimal"
            step="any"
            min={0}
            max={1000}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (dirty && !pending) save()
              }
            }}
            placeholder="—"
            disabled={pending}
            className="w-24 rounded-md border border-gray-300 bg-white px-2 py-1 text-right text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
          />
          <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
        </div>
        {error ? (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>
        ) : null}
      </td>
      <td className="px-3 py-2 align-middle">
        {dirty ? (
          <button
            type="button"
            onClick={save}
            disabled={pending}
            className="rounded-md bg-indigo-500 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
          >
            {pending ? '…' : 'Save'}
          </button>
        ) : savedTick > 0 ? (
          <span
            key={savedTick}
            className="inline-flex items-center text-green-600 dark:text-green-400"
            title="Saved"
          >
            <CheckIcon className="size-4" />
          </span>
        ) : null}
      </td>
    </tr>
  )
}
