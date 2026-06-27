'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline'

import {
  saveInvoiceAction,
  savePricingAction,
  setVendorPaidAction,
} from '@/app/(app)/work-orders/[id]/markup-actions'
import type { WorkOrderDetail } from '@/lib/api/types'
import { money, relativeTime } from '@/lib/format'

function num(s: string | null | undefined): number {
  if (!s) return 0
  const n = Number(s)
  return Number.isFinite(n) ? n : 0
}

type PriceMode = 'percent' | 'total' | 'profit'

const PRICE_MODES: { key: PriceMode; label: string }[] = [
  { key: 'percent', label: 'Markup %' },
  { key: 'total', label: 'Total bill' },
  { key: 'profit', label: 'Profit' },
]

/** Canonical markup % derived from whichever unit the operator typed in.
 *  We always persist the percent (Numeric(6,2)); total/profit are just
 *  friendlier ways to arrive at it. Null = nothing usable entered. */
function deriveMarkupPct(
  input: string,
  mode: PriceMode,
  subtotal: number,
): number | null {
  const v = Number(input)
  if (input.trim() === '' || !Number.isFinite(v)) return null
  if (mode === 'percent') return v
  if (subtotal <= 0) return null // can't derive a % from $ without a cost basis
  if (mode === 'total') return (v / subtotal - 1) * 100
  return (v / subtotal) * 100 // profit
}

/** "75.00" -> "75", "38.50" -> "38.5" for tidy display in the input. */
function trimNum(n: number): string {
  return n.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')
}

export function MarkupHelper({
  wo,
  defaultOpen = false,
}: {
  wo: WorkOrderDetail
  defaultOpen?: boolean
}) {
  const router = useRouter()
  // Vendor cost is itemized per assigned vendor (their labor + material).
  // When no vendor is assigned, fall back to one legacy unattributed row.
  const assignments = wo.vendor_assignments
  const hasAssignments = assignments.length > 0
  const [rows, setRows] = useState<CostRowState[]>(() =>
    hasAssignments
      ? assignments.map((a) => ({
          vendorId: a.vendor.id,
          name: a.vendor.name,
          labor: a.labor_cost ?? '',
          material: a.material_cost ?? '',
        }))
      : [
          {
            vendorId: null,
            name: 'Vendor cost',
            labor: wo.brenk_labor_cost ?? '',
            material: wo.brenk_material_cost ?? '',
          },
        ],
  )
  function setRow(i: number, patch: Partial<CostRowState>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  }
  const hasOverride =
    wo.brenk_total_override !== null && wo.brenk_total_override !== undefined
  const initialMarkup =
    wo.brenk_markup_percent ?? wo.suggested_markup_percent ?? ''
  // Daryl can drive pricing in whichever unit he thinks in: markup %,
  // the final total bill, or the profit. `priceInput` holds the raw text
  // of the active unit. If this WO was priced by a direct total, open in
  // "Total bill" mode showing that number.
  const [priceMode, setPriceMode] = useState<PriceMode>(
    hasOverride ? 'total' : 'percent',
  )
  const [priceInput, setPriceInput] = useState<string>(
    hasOverride ? trimNum(Number(wo.brenk_total_override)) : initialMarkup,
  )
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [savedTick, setSavedTick] = useState(0)

  // Backend-computed suggestion: category average (≥3 jobs) else trade
  // default, with a human label explaining which.
  const suggested = wo.suggested_markup_percent ?? null
  const suggestedLabel = wo.suggested_markup_label ?? null
  const isPriced = wo.brenk_markup_percent !== null || hasOverride
  const nte = wo.nte ? Number(wo.nte) : null

  // Live calculation: subtotal = Σ each vendor's (labor + material); total =
  // subtotal × (1 + markup/100); profit = total − subtotal. The canonical
  // markup % is derived from whatever unit Daryl edits in.
  const subtotal = rows.reduce((s, r) => s + num(r.labor) + num(r.material), 0)
  const haveCost = subtotal > 0

  // Direct-total path: in "Total bill" mode with no vendor cost entered,
  // the number Daryl types IS the (pre-tax) total — stored verbatim as
  // brenk_total_override, markup % stays unknown. The moment a vendor
  // cost exists we fall back to deriving a real markup %.
  const directTotal = priceMode === 'total' && !haveCost
  const directTotalVal = (() => {
    if (!directTotal) return null
    const v = Number(priceInput)
    return priceInput.trim() !== '' && Number.isFinite(v) && v > 0 ? v : null
  })()

  const markupPct = directTotal
    ? null
    : deriveMarkupPct(priceInput, priceMode, subtotal)
  const liveTotal = directTotal
    ? directTotalVal
    : haveCost && markupPct !== null
      ? subtotal * (1 + markupPct / 100)
      : null
  const liveProfit =
    !directTotal && haveCost && markupPct !== null
      ? subtotal * (markupPct / 100)
      : null
  const overNte = nte !== null && liveTotal !== null && liveTotal > nte

  // What we persist: in direct-total mode, the override; otherwise the
  // canonical markup %. The two are mutually exclusive — saving one
  // clears the other.
  const markupForSave = markupPct !== null ? markupPct.toFixed(2) : ''
  const overrideForSave =
    directTotal && directTotalVal !== null ? directTotalVal.toFixed(2) : ''

  function switchMode(next: PriceMode) {
    // Carry the current value over into the new unit so toggling doesn't reset it.
    if (next === 'percent') {
      setPriceInput(markupPct !== null ? trimNum(markupPct) : '')
    } else if (next === 'total') {
      // Carry a known total if we have one; otherwise leave blank so
      // Daryl can type the total directly (the no-cost override path).
      setPriceInput(liveTotal !== null ? liveTotal.toFixed(2) : '')
    } else {
      setPriceInput(markupPct !== null && haveCost ? liveProfit!.toFixed(2) : '')
    }
    setPriceMode(next)
  }

  const attribution = hasOverride
    ? `Total set ${formatRelative(wo.brenk_marked_up_at)} · editable below`
    : wo.brenk_markup_percent !== null
      ? `Markup set ${formatRelative(wo.brenk_marked_up_at)} · editable below`
      : suggested !== null && suggestedLabel
        ? `Suggested ${Number(suggested).toFixed(0)}% (${suggestedLabel})`
        : 'No suggestion yet — pick a markup manually'

  function save() {
    setError(null)
    if (overNte) {
      setError(
        `Total bill exceeds NTE ${money(wo.nte)}. The client won't accept an invoice above this — lower the markup or talk to the client about raising NTE.`,
      )
      return
    }
    startTransition(async () => {
      // markup % and a direct total are mutually exclusive — saving one clears
      // the other. With assignments, costs go per-vendor via the pricing
      // endpoint; without, the legacy single-cost PATCH.
      const pricing = directTotal
        ? { markup_percent: '', total_override: overrideForSave }
        : { markup_percent: markupForSave, total_override: '' }
      const result = hasAssignments
        ? await savePricingAction(wo.id, {
            costs: rows.map((r) => ({
              vendor_id: r.vendorId as number,
              labor_cost: r.labor,
              material_cost: r.material,
            })),
            ...pricing,
          })
        : await saveInvoiceAction(wo.id, {
            labor_cost: rows[0].labor,
            material_cost: rows[0].material,
            ...pricing,
          })
      if (result.error) setError(result.error)
      else setSavedTick((n) => n + 1)
    })
  }

  function clearMarkup() {
    setError(null)
    startTransition(async () => {
      const result = await saveInvoiceAction(wo.id, {
        markup_percent: '',
        total_override: '',
      })
      if (result.error) setError(result.error)
      else {
        setPriceMode('percent')
        setPriceInput('')
        setSavedTick((n) => n + 1)
      }
    })
  }

  const savedMarkup = wo.brenk_markup_percent
    ? Number(wo.brenk_markup_percent).toFixed(2)
    : ''
  const savedOverride = hasOverride
    ? Number(wo.brenk_total_override).toFixed(2)
    : ''
  // What save() would write for the two pricing fields, given the active
  // path. Dirty if any per-vendor cost / markup / override changes.
  const nextMarkup = directTotal ? '' : markupForSave
  const nextOverride = directTotal ? overrideForSave : ''
  const costsDirty = hasAssignments
    ? rows.some(
        (r, i) =>
          r.labor !== (assignments[i]?.labor_cost ?? '') ||
          r.material !== (assignments[i]?.material_cost ?? ''),
      )
    : rows[0].labor !== (wo.brenk_labor_cost ?? '') ||
      rows[0].material !== (wo.brenk_material_cost ?? '')
  const canSubmit =
    !pending &&
    (costsDirty || nextMarkup !== savedMarkup || nextOverride !== savedOverride)

  function togglePaid(vendorId: number, mark: boolean) {
    setError(null)
    startTransition(async () => {
      const result = await setVendorPaidAction(wo.id, vendorId, mark)
      if (result.error) setError(result.error)
      else router.refresh()
    })
  }

  return (
    <details
      open={defaultOpen}
      className="group rounded-lg ring-1 ring-gray-200 dark:ring-white/10 [&_summary::-webkit-details-marker]:hidden"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 group-open:border-b group-open:border-gray-200 dark:group-open:border-white/10">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            Markup helper
          </h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {attribution}
          </p>
        </div>
        <ChevronDownIcon className="size-4 shrink-0 text-gray-400 transition-transform group-open:rotate-180" />
      </summary>

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

        {/* Per-vendor payouts — what Brenk pays each sub-vendor. */}
        {rows.map((r, i) => (
          <VendorCostRow
            key={r.vendorId ?? 'legacy'}
            row={r}
            onChange={(patch) => setRow(i, patch)}
            disabled={pending}
            paidAt={hasAssignments ? (assignments[i]?.paid_to_vendor_at ?? null) : null}
            onTogglePaid={
              r.vendorId !== null
                ? (mark) => togglePaid(r.vendorId as number, mark)
                : undefined
            }
          />
        ))}

        {/* Subtotal (total vendor cost) — derived, not editable */}
        <div className="flex items-baseline justify-between border-t border-gray-100 pt-2 text-xs dark:border-white/10">
          <span className="text-gray-500 dark:text-gray-400">
            {rows.length > 1 ? 'Total vendor cost' : 'Vendor cost'}
          </span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {subtotal > 0 ? money(subtotal.toFixed(2)) : '—'}
          </span>
        </div>

        {/* Drive pricing by markup %, total bill, or profit, whichever
            Daryl thinks in. We persist the derived markup % either way. */}
        <div className="flex items-center justify-between gap-2 border-t border-gray-100 pt-2 dark:border-white/10">
          <span className="text-xs text-gray-500 dark:text-gray-400">Set by</span>
          <div className="inline-flex rounded-md bg-gray-100 p-0.5 dark:bg-white/5">
            {PRICE_MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => switchMode(m.key)}
                disabled={pending}
                className={
                  priceMode === m.key
                    ? 'rounded bg-white px-2 py-0.5 text-xs font-medium text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                    : 'rounded px-2 py-0.5 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor="price_input" className="text-gray-500 dark:text-gray-400">
            {priceMode === 'percent'
              ? 'Markup'
              : priceMode === 'total'
                ? 'Total bill'
                : 'Profit'}
          </label>
          <div className="flex items-center gap-1">
            {priceMode !== 'percent' ? (
              <span className="text-sm text-gray-500 dark:text-gray-400">$</span>
            ) : null}
            <input
              id="price_input"
              type="number"
              inputMode="decimal"
              step="any"
              min={0}
              value={priceInput}
              onChange={(e) => setPriceInput(e.target.value)}
              disabled={pending || (priceMode === 'profit' && !haveCost)}
              className="w-24 rounded-md border border-gray-300 bg-white px-2 py-1 text-right text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-white/10 dark:bg-gray-800 dark:text-white"
            />
            {priceMode === 'percent' ? (
              <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
            ) : null}
          </div>
        </div>
        {priceMode === 'profit' && !haveCost ? (
          <p className="text-right text-xs text-gray-400">
            Enter a labor or material cost first.
          </p>
        ) : null}
        {directTotal && directTotalVal !== null ? (
          <p className="text-right text-xs text-gray-400">
            Billing the total directly — no vendor cost on file, so margin
            isn’t tracked. Add a labor/material cost to capture the markup.
          </p>
        ) : null}

        {/* Derived read-outs: markup %, total bill, and what Brenk makes. */}
        <div className="space-y-1.5 border-t border-gray-100 pt-2 dark:border-white/10">
          <SummaryRow
            label="Markup"
            value={markupPct !== null ? `${trimNum(markupPct)}%` : '—'}
          />
          <SummaryRow
            label="Total bill"
            value={liveTotal !== null ? money(liveTotal.toFixed(2)) : '—'}
            strong
            tone={overNte ? 'danger' : undefined}
          />
          <SummaryRow
            label="Total profit"
            value={liveProfit !== null ? money(liveProfit.toFixed(2)) : '—'}
            strong
            tone="profit"
          />
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
          {isPriced ? (
            <button
              type="button"
              onClick={clearMarkup}
              disabled={pending}
              title="Clear pricing and return to Ready to mark up (costs stay)"
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
    </details>
  )
}

type CostRowState = {
  vendorId: number | null
  name: string
  labor: string
  material: string
}

function VendorCostRow({
  row,
  onChange,
  disabled,
  paidAt,
  onTogglePaid,
}: {
  row: CostRowState
  onChange: (patch: Partial<CostRowState>) => void
  disabled: boolean
  paidAt: string | null
  /** Present only for real vendor assignments (not the legacy row). */
  onTogglePaid?: (mark: boolean) => void
}) {
  const payout = num(row.labor) + num(row.material)
  return (
    <div className="rounded-md bg-gray-50 px-2.5 py-2 dark:bg-white/5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-gray-800 dark:text-gray-100">
          {row.name}
        </span>
        {onTogglePaid ? (
          paidAt ? (
            <button
              type="button"
              onClick={() => onTogglePaid(false)}
              disabled={disabled}
              className="inline-flex items-center gap-1 text-xs text-emerald-700 hover:underline disabled:opacity-60 dark:text-emerald-400"
              title="Brenk paid this vendor — click to undo"
            >
              <CheckCircleIcon className="size-3.5" />
              Paid {relativeTime(paidAt)}
            </button>
          ) : payout > 0 ? (
            <button
              type="button"
              onClick={() => onTogglePaid(true)}
              disabled={disabled}
              className="rounded-md bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              Mark paid
            </button>
          ) : null
        ) : null}
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <MoneyInput
          label="Labor"
          value={row.labor}
          onChange={(v) => onChange({ labor: v })}
          disabled={disabled}
        />
        <MoneyInput
          label="Material"
          value={row.material}
          onChange={(v) => onChange({ material: v })}
          disabled={disabled}
        />
        <span className="ml-auto text-xs font-medium text-gray-600 dark:text-gray-300">
          {payout > 0 ? money(payout.toFixed(2)) : '—'}
        </span>
      </div>
    </div>
  )
}

function MoneyInput({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  disabled: boolean
}) {
  return (
    <label className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
      {label}
      <span>$</span>
      <input
        type="number"
        inputMode="decimal"
        step="any"
        min={0}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0"
        disabled={disabled}
        className="w-20 rounded-md border border-gray-300 bg-white px-2 py-1 text-right text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
      />
    </label>
  )
}

function SummaryRow({
  label,
  value,
  strong,
  tone,
}: {
  label: string
  value: string
  strong?: boolean
  tone?: 'danger' | 'profit'
}) {
  const valueColor =
    tone === 'danger'
      ? 'text-red-700 dark:text-red-400'
      : tone === 'profit'
        ? 'text-emerald-700 dark:text-emerald-400'
        : 'text-gray-900 dark:text-white'
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
      <span
        className={`${strong ? 'text-base font-semibold' : 'text-sm font-medium'} ${valueColor}`}
      >
        {value}
      </span>
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
