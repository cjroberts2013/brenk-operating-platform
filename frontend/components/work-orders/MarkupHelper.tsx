'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline'

import {
  saveInvoiceAction,
  setPaidAction,
} from '@/app/(app)/work-orders/[id]/markup-actions'
import type { WorkOrderDetail } from '@/lib/api/types'
import { money } from '@/lib/format'

function num(s: string | null | undefined): number {
  if (!s) return 0
  const n = Number(s)
  return Number.isFinite(n) ? n : 0
}

export function MarkupHelper({ wo }: { wo: WorkOrderDetail }) {
  // Three inputs, all locally controlled. Labor and material together
  // form the vendor cost; markup applies to their sum.
  const [labor, setLabor] = useState<string>(wo.brenk_labor_cost ?? '')
  const [material, setMaterial] = useState<string>(wo.brenk_material_cost ?? '')
  const initialMarkup =
    wo.brenk_markup_percent ?? wo.trade?.default_markup_percent ?? ''
  const [markup, setMarkup] = useState<string>(initialMarkup)
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [savedTick, setSavedTick] = useState(0)

  const tradeDefault = wo.trade?.default_markup_percent ?? null
  const tradeName = wo.trade?.name ?? null
  const chosenMarkup = wo.brenk_markup_percent
  const isPaid = Boolean(wo.brenk_paid_at)
  const nte = wo.nte ? Number(wo.nte) : null

  // Live calculation: subtotal = labor + material; total = subtotal × (1 + markup/100).
  const laborN = num(labor)
  const materialN = num(material)
  const subtotal = laborN + materialN
  const markupN = num(markup)
  const haveCost = subtotal > 0
  const haveMarkup = markup.trim().length > 0
  const liveTotal = haveCost && haveMarkup ? subtotal * (1 + markupN / 100) : null
  const overNte = nte !== null && liveTotal !== null && liveTotal > nte

  const attribution = chosenMarkup
    ? `Markup set ${formatRelative(wo.brenk_marked_up_at)} · editable below`
    : tradeDefault && tradeName
      ? `Suggested ${Number(tradeDefault).toFixed(0)}% (${tradeName} default)`
      : tradeName
        ? `No default set for ${tradeName} yet — set one in Settings`
        : 'No trade on this WO; pick a markup manually'

  function save() {
    setError(null)
    if (overNte) {
      setError(
        `Total bill exceeds NTE ${money(wo.nte)}. The client won't accept an invoice above this — lower the markup or talk to the client about raising NTE.`,
      )
      return
    }
    startTransition(async () => {
      const result = await saveInvoiceAction(wo.id, {
        labor_cost: labor,
        material_cost: material,
        markup_percent: markup,
      })
      if (result.error) setError(result.error)
      else setSavedTick((n) => n + 1)
    })
  }

  function clearMarkup() {
    setError(null)
    startTransition(async () => {
      const result = await saveInvoiceAction(wo.id, { markup_percent: '' })
      if (result.error) setError(result.error)
      else {
        setMarkup('')
        setSavedTick((n) => n + 1)
      }
    })
  }

  function togglePaid() {
    setError(null)
    startTransition(async () => {
      const result = await setPaidAction(wo.id, !isPaid)
      if (result.error) setError(result.error)
    })
  }

  const canSubmit =
    !pending &&
    (labor !== (wo.brenk_labor_cost ?? '') ||
      material !== (wo.brenk_material_cost ?? '') ||
      markup !== (wo.brenk_markup_percent ?? ''))

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Markup helper
        </h2>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          {attribution}
        </p>
      </header>

      <div className="flex items-start gap-1.5 border-b border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-600 dark:border-white/10 dark:bg-gray-800/40 dark:text-gray-400">
        <LockClosedIcon className="mt-0.5 size-3 shrink-0 text-gray-400" />
        <span>
          Vendor costs and markup stay private to Brenk. Never sent to
          ServiceChannel — only the final total bill, which Daryl enters into
          SC manually.
        </span>
      </div>

      <div className="space-y-2.5 px-4 py-3 text-sm">
        {/* NTE — read-only ceiling reference */}
        <div className="flex items-baseline justify-between text-xs">
          <span className="text-gray-500 dark:text-gray-400">
            NTE (max billable to client)
          </span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {money(wo.nte, wo.currency_code || 'USD')}
          </span>
        </div>

        <CostRow
          id="labor_cost"
          label="Labor cost"
          sublabel="vendor's labor charge"
          value={labor}
          onChange={setLabor}
          disabled={pending}
        />
        <CostRow
          id="material_cost"
          label="Material cost"
          sublabel="parts / materials"
          value={material}
          onChange={setMaterial}
          disabled={pending}
        />

        {/* Subtotal (vendor cost) — derived, not editable */}
        <div className="flex items-baseline justify-between border-t border-gray-100 pt-2 text-xs dark:border-white/10">
          <span className="text-gray-500 dark:text-gray-400">
            Vendor cost (subtotal)
          </span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {subtotal > 0 ? money(subtotal.toFixed(2)) : '—'}
          </span>
        </div>

        <div className="flex items-baseline justify-between gap-3">
          <label
            htmlFor="markup_pct"
            className="text-gray-500 dark:text-gray-400"
          >
            Markup
          </label>
          <div className="flex items-center gap-1">
            <input
              id="markup_pct"
              type="number"
              inputMode="decimal"
              step="any"
              min={0}
              max={1000}
              value={markup}
              onChange={(e) => setMarkup(e.target.value)}
              disabled={pending}
              className="w-20 rounded-md border border-gray-300 bg-white px-2 py-1 text-right text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
            />
            <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
          </div>
        </div>

        <div className="flex items-baseline justify-between border-t border-gray-100 pt-2 dark:border-white/10">
          <span className="text-gray-500 dark:text-gray-400">Total bill</span>
          <span
            className={
              overNte
                ? 'text-base font-semibold text-red-700 dark:text-red-400'
                : 'text-base font-semibold text-gray-900 dark:text-white'
            }
          >
            {liveTotal !== null ? money(liveTotal.toFixed(2)) : '—'}
          </span>
        </div>

        {overNte ? (
          <div className="flex items-start gap-1.5 rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
            <ExclamationTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
            <span>
              Total bill is over NTE ({money(wo.nte)}). The client won&apos;t
              accept an invoice above NTE — lower the markup, lower the vendor
              cost, or talk to the client about raising NTE.
            </span>
          </div>
        ) : null}

        {error ? (
          <p className="rounded-md bg-red-50 px-2 py-1 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        ) : null}

        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={save}
            disabled={!canSubmit}
            className="flex-1 rounded-md bg-indigo-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
          >
            {pending ? 'Saving…' : 'Save'}
          </button>
          {chosenMarkup ? (
            <button
              type="button"
              onClick={clearMarkup}
              disabled={pending}
              title="Clear markup and return to Ready to mark up (costs stay)"
              className="rounded-md px-2 py-1.5 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5"
            >
              Clear markup
            </button>
          ) : null}
          {savedTick > 0 ? (
            <span
              key={savedTick}
              className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400"
              title="Saved"
            >
              <CheckCircleIcon className="size-4" />
              Saved
            </span>
          ) : null}
        </div>
      </div>

      <div className="border-t border-gray-200 px-4 py-3 dark:border-white/10">
        {isPaid ? (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400">
              <CheckCircleIcon className="size-4" />
              Marked paid {formatRelative(wo.brenk_paid_at)}
            </div>
            <button
              type="button"
              onClick={togglePaid}
              disabled={pending}
              className="text-xs text-gray-500 underline hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Undo (clear paid date)
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={togglePaid}
            disabled={pending}
            className="w-full rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
          >
            Mark paid
          </button>
        )}
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Use this once the client has paid Brenk for this work. Moves the WO
          to the{' '}
          <Link
            href="/invoices?tab=paid"
            className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
          >
            Paid
          </Link>{' '}
          tab.
        </p>
      </div>
    </section>
  )
}

function CostRow({
  id,
  label,
  sublabel,
  value,
  onChange,
  disabled,
}: {
  id: string
  label: string
  sublabel: string
  value: string
  onChange: (v: string) => void
  disabled: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <label htmlFor={id} className="text-gray-500 dark:text-gray-400">
        {label}
        <span className="ml-1 text-[10px] uppercase tracking-wide text-gray-400">
          ({sublabel})
        </span>
      </label>
      <div className="flex items-center gap-1">
        <span className="text-sm text-gray-500 dark:text-gray-400">$</span>
        <input
          id={id}
          type="number"
          inputMode="decimal"
          step="any"
          min={0}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="0.00"
          disabled={disabled}
          className="w-24 rounded-md border border-gray-300 bg-white px-2 py-1 text-right text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
        />
      </div>
    </div>
  )
}

function formatRelative(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diffMs = Date.now() - d.getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}
