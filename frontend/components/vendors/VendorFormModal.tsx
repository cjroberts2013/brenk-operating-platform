'use client'

import { useActionState, useEffect, useMemo, useRef, useState } from 'react'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import { PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'

import {
  createTradeAction,
  createVendorAction,
  updateVendorAction,
  type VendorActionState,
} from '@/app/(app)/vendors/actions'
import type { TradeRef, VendorSummary } from '@/lib/api/types'

const INITIAL_STATE: VendorActionState = { error: null, attempt: 0 }

const CONTACT_OPTIONS = [
  { value: '', label: '— No preference —' },
  { value: 'sms', label: 'Text (SMS)' },
  { value: 'call', label: 'Phone call' },
  { value: 'email', label: 'Email' },
  { value: 'other', label: 'Other' },
]

const MOBILE_APP_OPTIONS = [
  { value: '', label: 'Unknown' },
  { value: 'yes', label: 'Yes — uses the CubeSmart app' },
  { value: 'no', label: 'No' },
]

export type VendorFormModalProps = {
  open: boolean
  onClose: () => void
  /** When set, the modal is in "edit" mode for this vendor. Null → "create". */
  vendor: VendorSummary | null
  trades: TradeRef[]
}

export function VendorFormModal({
  open,
  onClose,
  vendor,
  trades,
}: VendorFormModalProps) {
  const isEdit = vendor !== null

  const [state, formAction, pending] = useActionState<VendorActionState, FormData>(
    isEdit ? updateVendorAction : createVendorAction,
    INITIAL_STATE,
  )

  // Close on successful submit. `attempt` is bumped by the action; the
  // ref tracks the last attempt we observed so we only close on a *new*
  // success (not on the initial mount with attempt=0).
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

  // Trade selection lives in client state so newly-created trades can be
  // appended + auto-selected without remounting the form. Resets when the
  // modal flips between vendors (the key on this component should change
  // — but as a safety net the effect below reconciles when `vendor` changes).
  const [tradesList, setTradesList] = useState<TradeRef[]>(trades)
  const [selectedTradeIds, setSelectedTradeIds] = useState<Set<number>>(
    () => new Set((vendor?.trade_specializations ?? []).map((t) => t.id)),
  )
  const [tradeQuery, setTradeQuery] = useState('')
  const [creatingTrade, setCreatingTrade] = useState(false)
  const [tradeCreateError, setTradeCreateError] = useState<string | null>(null)

  // When the parent swaps which vendor is being edited (modal stays
  // mounted across opens), resync the selected trades to the new vendor.
  useEffect(() => {
    setSelectedTradeIds(
      new Set((vendor?.trade_specializations ?? []).map((t) => t.id)),
    )
    setTradeQuery('')
    setTradeCreateError(null)
  }, [vendor?.id])

  // Also keep the local trades list in sync if the parent passes more
  // (rare — usually only happens on initial mount and after a successful
  // create that revalidates the page).
  useEffect(() => {
    setTradesList((prev) => {
      // Merge: keep any locally-created trades not in the new list.
      const seen = new Set(trades.map((t) => t.id))
      const localOnly = prev.filter((t) => !seen.has(t.id))
      return [...trades, ...localOnly].sort((a, b) =>
        a.name.localeCompare(b.name),
      )
    })
  }, [trades])

  const filteredTrades = useMemo(() => {
    const q = tradeQuery.trim().toLowerCase()
    if (!q) return tradesList
    return tradesList.filter((t) => t.name.toLowerCase().includes(q))
  }, [tradesList, tradeQuery])

  const showCreateOption =
    tradeQuery.trim().length > 0 && filteredTrades.length === 0

  function toggleTrade(id: number) {
    setSelectedTradeIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleCreateTrade() {
    const name = tradeQuery.trim()
    if (!name || creatingTrade) return
    setCreatingTrade(true)
    setTradeCreateError(null)
    const result = await createTradeAction(name)
    setCreatingTrade(false)
    if (result.error) {
      setTradeCreateError(result.error)
      return
    }
    if (result.trade) {
      const newTrade = result.trade
      setTradesList((prev) =>
        [...prev, newTrade].sort((a, b) => a.name.localeCompare(b.name)),
      )
      setSelectedTradeIds((prev) => new Set([...prev, newTrade.id]))
      setTradeQuery('')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-gray-900/70 transition-opacity duration-200 data-closed:opacity-0"
      />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel
          transition
          className="relative w-full max-w-2xl rounded-lg bg-white shadow-xl ring-1 ring-black/5 transition duration-200 data-closed:translate-y-2 data-closed:opacity-0 dark:bg-gray-900 dark:ring-white/10"
        >
          <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-white/10">
            <DialogTitle className="text-base font-semibold text-gray-900 dark:text-white">
              {isEdit ? `Edit vendor — ${vendor!.name}` : 'Add vendor'}
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
            {isEdit ? (
              <input type="hidden" name="id" value={vendor!.id} />
            ) : null}

            <Row>
              <Field label="Name" required>
                <input
                  type="text"
                  name="name"
                  required
                  defaultValue={vendor?.name ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Active">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="is_active"
                    defaultChecked={vendor?.is_active ?? true}
                    className="rounded border-gray-300 text-indigo-500 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Currently active
                  </span>
                </label>
              </Field>
            </Row>

            <Row>
              <Field label="Phone">
                <input
                  type="tel"
                  name="phone"
                  defaultValue={vendor?.phone ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Email">
                <input
                  type="email"
                  name="email"
                  defaultValue={vendor?.email ?? ''}
                  className={inputClass}
                />
              </Field>
            </Row>

            <Row>
              <Field label="Preferred contact">
                <select
                  name="contact_preference"
                  defaultValue={vendor?.contact_preference ?? ''}
                  className={inputClass}
                >
                  {CONTACT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Mobile-app capable">
                <select
                  name="mobile_app_capable"
                  defaultValue={
                    vendor?.mobile_app_capable === true
                      ? 'yes'
                      : vendor?.mobile_app_capable === false
                        ? 'no'
                        : ''
                  }
                  className={inputClass}
                >
                  {MOBILE_APP_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
            </Row>

            <Field label="Payment terms">
              <input
                type="text"
                name="payment_terms"
                placeholder="e.g. Invoices weekly · Hourly · Flat per job"
                defaultValue={vendor?.payment_terms ?? ''}
                className={inputClass}
              />
            </Field>

            <Field label="Trade specializations">
              {tradesList.length === 0 && !tradeQuery ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No trades available yet — run a work-order sync to
                  populate the trades table, or type a name below to
                  create one.
                </p>
              ) : null}

              <input
                type="search"
                value={tradeQuery}
                onChange={(e) => {
                  setTradeQuery(e.target.value)
                  if (tradeCreateError) setTradeCreateError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && showCreateOption) {
                    // Prevent submitting the outer form when the user
                    // hits Enter to confirm trade creation.
                    e.preventDefault()
                    void handleCreateTrade()
                  }
                }}
                placeholder="Search trades… or type a new one to create"
                className={`mb-2 ${inputClass}`}
              />

              {/* Hidden inputs carry the selected trade ids into the form
                  submission — keeps the FormData.getAll('trade_ids')
                  contract that the server action expects. */}
              {[...selectedTradeIds].map((id) => (
                <input
                  key={id}
                  type="hidden"
                  name="trade_ids"
                  value={id}
                />
              ))}

              <div className="flex flex-wrap gap-1.5">
                {filteredTrades.map((trade) => {
                  const selected = selectedTradeIds.has(trade.id)
                  return (
                    <button
                      key={trade.id}
                      type="button"
                      onClick={() => toggleTrade(trade.id)}
                      className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition-colors ${
                        selected
                          ? 'bg-indigo-500 text-white ring-indigo-400 dark:bg-indigo-500 dark:text-white dark:ring-indigo-400'
                          : 'bg-gray-100 text-gray-700 ring-gray-300 hover:bg-gray-200 dark:bg-white/5 dark:text-gray-300 dark:ring-white/10 dark:hover:bg-white/10'
                      }`}
                    >
                      {trade.name}
                    </button>
                  )
                })}
                {showCreateOption ? (
                  <button
                    type="button"
                    onClick={handleCreateTrade}
                    disabled={creatingTrade}
                    className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-500/30 hover:bg-green-500/20 disabled:opacity-60 dark:text-green-300"
                  >
                    <PlusIcon className="size-3" />
                    {creatingTrade
                      ? 'Creating…'
                      : `Create "${tradeQuery.trim()}"`}
                  </button>
                ) : null}
              </div>

              {tradeCreateError ? (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                  {tradeCreateError}
                </p>
              ) : null}
            </Field>

            <Field label="Markup notes">
              <textarea
                name="markup_notes"
                rows={2}
                placeholder="e.g. Premium work, run higher markup."
                defaultValue={vendor?.markup_notes ?? ''}
                className={inputClass}
              />
            </Field>

            <Field label="Communication notes">
              <textarea
                name="communication_notes"
                rows={2}
                placeholder="e.g. Don't text after 6pm. Responds slowly."
                defaultValue={vendor?.communication_notes ?? ''}
                className={inputClass}
              />
            </Field>

            <Field label="General notes">
              <textarea
                name="notes"
                rows={2}
                defaultValue={vendor?.notes ?? ''}
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
                {pending
                  ? 'Saving…'
                  : isEdit
                    ? 'Save changes'
                    : 'Add vendor'}
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
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
        {label}
        {required ? <span className="ml-0.5 text-red-500">*</span> : null}
      </label>
      {children}
    </div>
  )
}
