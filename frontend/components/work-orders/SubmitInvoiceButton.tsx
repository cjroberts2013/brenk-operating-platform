'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react'
import {
  ExclamationTriangleIcon,
  LockClosedIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline'

import {
  previewInvoiceAction,
  submitInvoiceAction,
} from '@/app/(app)/work-orders/[id]/markup-actions'
import type { InvoiceSubmitPreview } from '@/lib/api/types'
import { money } from '@/lib/format'

/**
 * "Submit to ServiceChannel" button + confirmation dialog.
 *
 * The dialog renders the SERVER-computed preview verbatim (invoice #,
 * marked-up amounts, total vs NTE) so what Daryl approves is exactly
 * what gets sent. The resolution text is editable here because the
 * client requires it on every invoice. Vendor costs and markup % are
 * never part of the payload.
 */
export function SubmitInvoiceButton({
  workOrderId,
  size = 'card',
}: {
  workOrderId: number
  /** 'card' = full-width button (WO detail rail); 'row' = compact (table row). */
  size?: 'card' | 'row'
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<InvoiceSubmitPreview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  async function openDialog() {
    setOpen(true)
    setLoading(true)
    setLoadError(null)
    setSubmitError(null)
    const result = await previewInvoiceAction(workOrderId)
    setPreview(result.preview)
    setLoadError(result.error)
    setText(result.preview?.resolution_text ?? '')
    setLoading(false)
  }

  // The resolution-text problem is fixable right here in the dialog;
  // every other problem needs action elsewhere (markup helper, SC).
  const blockingProblems = (preview?.problems ?? []).filter(
    (p) => !(p.startsWith('Resolution text') && text.trim().length > 0),
  )
  const canSubmit =
    !pending && !loading && preview !== null && blockingProblems.length === 0

  function submit() {
    setSubmitError(null)
    startTransition(async () => {
      const result = await submitInvoiceAction(workOrderId, text.trim() || null)
      if (result.error) {
        setSubmitError(result.error)
      } else {
        setOpen(false)
        router.refresh()
      }
    })
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className={
          size === 'card'
            ? 'inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500'
            : 'inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-500'
        }
      >
        <PaperAirplaneIcon className={size === 'card' ? 'size-4' : 'size-3.5'} />
        Submit to ServiceChannel
      </button>

      <Dialog open={open} onClose={setOpen} className="relative z-50">
        <DialogBackdrop
          transition
          className="fixed inset-0 bg-gray-900/60 transition-opacity data-closed:opacity-0"
        />
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel
            transition
            className="w-full max-w-md rounded-lg bg-white shadow-xl ring-1 ring-gray-200 transition data-closed:scale-95 data-closed:opacity-0 dark:bg-gray-900 dark:ring-white/10"
          >
            <div className="border-b border-gray-200 px-5 py-4 dark:border-white/10">
              <DialogTitle className="text-base font-semibold text-gray-900 dark:text-white">
                Submit invoice to ServiceChannel
              </DialogTitle>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                Review what will be sent. This creates a real invoice for the
                client.
              </p>
            </div>

            <div className="space-y-3 px-5 py-4 text-sm">
              {loading ? (
                <p className="py-4 text-center text-gray-500 dark:text-gray-400">
                  Loading preview…
                </p>
              ) : loadError ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
                  {loadError}
                </p>
              ) : preview ? (
                <>
                  <Row label="Invoice #">
                    <span className="font-medium text-gray-900 dark:text-white">
                      {preview.invoice_number}
                    </span>
                  </Row>
                  <Row label="Labor (marked up)">{money(preview.labor_amount)}</Row>
                  <Row label="Material (marked up)">
                    {money(preview.material_amount)}
                  </Row>
                  <Row label="Subtotal">{money(preview.subtotal)}</Row>
                  <Row label="Sales tax (8.25%)">{money(preview.tax_amount)}</Row>
                  <div className="flex items-baseline justify-between border-t border-gray-100 pt-2 dark:border-white/10">
                    <span className="text-gray-500 dark:text-gray-400">
                      Total bill
                    </span>
                    <span className="text-base font-semibold text-gray-900 dark:text-white">
                      {money(preview.invoice_total)}
                    </span>
                  </div>
                  <Row label="NTE (client max)">{money(preview.nte)}</Row>

                  <div>
                    <label
                      htmlFor="invoice_text"
                      className="text-xs font-medium text-gray-700 dark:text-gray-300"
                    >
                      Work description (required by the client)
                    </label>
                    <textarea
                      id="invoice_text"
                      rows={3}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      disabled={pending}
                      placeholder="Describe the work completed…"
                      className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
                    />
                  </div>

                  {blockingProblems.length > 0 ? (
                    <div className="space-y-1 rounded-md bg-red-50 px-3 py-2 dark:bg-red-950/40">
                      {blockingProblems.map((p) => (
                        <p
                          key={p}
                          className="flex items-start gap-1.5 text-xs text-red-700 dark:text-red-300"
                        >
                          <ExclamationTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                          {p}
                        </p>
                      ))}
                    </div>
                  ) : null}

                  <div className="flex items-start gap-1.5 rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:bg-gray-800/40 dark:text-gray-400">
                    <LockClosedIcon className="mt-0.5 size-3 shrink-0 text-gray-400" />
                    <span>
                      Only these marked-up amounts are sent. Vendor costs and
                      markup % stay private to Brenk.
                    </span>
                  </div>

                  {submitError ? (
                    <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
                      {submitError}
                    </p>
                  ) : null}
                </>
              ) : null}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-gray-200 px-5 py-3 dark:border-white/10">
              <button
                type="button"
                onClick={() => setOpen(false)}
                disabled={pending}
                className="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={!canSubmit}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {pending ? 'Submitting…' : 'Submit invoice'}
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-gray-700 dark:text-gray-300">{children}</span>
    </div>
  )
}
