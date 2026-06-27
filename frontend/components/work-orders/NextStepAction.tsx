import type { ReactNode } from 'react'

import {
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
} from '@heroicons/react/20/solid'

import type { VendorSummary, WorkOrderDetail } from '@/lib/api/types'

import { deriveNextStep } from './next-step'

/** Human label for a vendor's preferred contact method. */
function preferredContactLabel(pref: string | null | undefined): string | null {
  switch (pref) {
    case 'sms':
      return 'Prefers text'
    case 'call':
      return 'Prefers a call'
    case 'email':
      return 'Prefers email'
    case 'other':
      return 'Preferred contact'
    default:
      return null
  }
}

/**
 * Action-first hero at the top of the WO detail page. Beyond naming the
 * single next step (like the old NextStepCard), it embeds the actual
 * control to perform that step — the vendor dropdown, the message card,
 * the markup helper, the submit button — so the operator never has to
 * hunt the right rail for the tool the WO needs right now.
 *
 * The heavy controls (markup helper, message card, submit button) are
 * built by the page and passed in; this component just decides which one
 * belongs in the hero for the current step. Steps that are waiting on
 * SC/the store/the vendor render as an informational banner only.
 */
export function NextStepAction({
  wo,
  scWebUrl,
  assignedVendor,
  vendorControl,
  notifyControl,
  messageCard,
  markupHelper,
  submitButton,
  paidControl,
}: {
  wo: WorkOrderDetail
  scWebUrl: string
  assignedVendor: VendorSummary | null
  /** VendorAssignmentControl — shown when the step is "assign". */
  vendorControl: ReactNode
  /** VendorNotifiedControl — shown alongside the message on "notify". */
  notifyControl: ReactNode
  /** MessageVendorCard — shown on "notify" (null if no vendor message). */
  messageCard: ReactNode | null
  /** MarkupHelper (open) — shown on the "markup"/"invoice" steps. */
  markupHelper: ReactNode | null
  /** SubmitInvoiceButton — shown on the "invoice" step (null otherwise). */
  submitButton: ReactNode | null
  /** MarkPaidControl — shown on the "paid"/"done" steps. */
  paidControl: ReactNode
}) {
  const step = deriveNextStep(wo)
  const done = step.kind === 'done'
  const waiting = step.owner === 'none' && !done

  const tone = done
    ? 'bg-emerald-50 ring-emerald-200 dark:bg-emerald-950/30 dark:ring-emerald-500/30'
    : waiting
      ? 'bg-gray-50 ring-gray-200 dark:bg-gray-800/40 dark:ring-white/10'
      : 'bg-indigo-50 ring-indigo-200 dark:bg-indigo-950/30 dark:ring-indigo-500/30'

  const eyebrow = done
    ? 'text-emerald-700 dark:text-emerald-400'
    : waiting
      ? 'text-gray-500 dark:text-gray-400'
      : 'text-indigo-700 dark:text-indigo-400'

  const action = renderAction()

  return (
    <section className={`rounded-lg p-4 ring-1 ${tone}`}>
      <div className="flex flex-col gap-1">
        <div
          className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${eyebrow}`}
        >
          {done ? <CheckCircleIcon className="size-4" /> : null}
          {done ? 'Complete' : waiting ? 'Status' : 'Next step'}
        </div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">
          {step.title}
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-300">{step.detail}</p>
      </div>

      {action ? (
        <div className="mt-3 rounded-md bg-white/70 p-3 dark:bg-gray-900/40">
          {action}
        </div>
      ) : null}
    </section>
  )

  function renderAction(): ReactNode {
    switch (step.kind) {
      case 'accept':
        return scLink('Accept in ServiceChannel')
      case 'assign':
        return vendorControl
      case 'notify':
        return (
          <div className="space-y-3">
            {assignedVendor ? <NotifyContact vendor={assignedVendor} /> : null}
            {messageCard}
            {notifyControl}
          </div>
        )
      case 'markup':
        return markupHelper
      case 'invoice':
        return (
          <div className="space-y-3">
            {markupHelper}
            {submitButton ? (
              <div>
                {submitButton}
                <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                  Or enter the total into SC&apos;s form yourself —{' '}
                  {scInline('open in ServiceChannel')}.
                </p>
              </div>
            ) : (
              scLink('Invoice in ServiceChannel')
            )}
          </div>
        )
      case 'paid':
      case 'done':
        // Invoiced (or already paid) — the only action left is recording
        // that the client paid Brenk. Its own control, not the markup tool.
        return paidControl
      default:
        // await-work / await-store / canceled — nothing to do.
        return null
    }
  }

  function scLink(label: string): ReactNode {
    return (
      <a
        href={`${scWebUrl}/sc/wo/Workorders/index?id=${wo.sc_work_order_id}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
      >
        {label}
        <ArrowTopRightOnSquareIcon className="size-4" />
      </a>
    )
  }

  function scInline(label: string): ReactNode {
    return (
      <a
        href={`${scWebUrl}/sc/wo/Workorders/index?id=${wo.sc_work_order_id}`}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
      >
        {label}
      </a>
    )
  }
}

/** Preferred-contact block shown on the "notify" step so Daryl can reach
 *  the assigned vendor the way they like, in one tap. */
function NotifyContact({ vendor }: { vendor: VendorSummary }) {
  const prefLabel = preferredContactLabel(vendor.contact_preference)
  const { phone, email, communication_notes: notes } = vendor
  const digits = phone ? phone.replace(/\D/g, '') : ''
  if (!prefLabel && !phone && !email && !notes) return null
  return (
    <div className="rounded-md bg-white px-3 py-2 ring-1 ring-gray-200 dark:bg-white/5 dark:ring-white/10">
      <div className="text-[11px] font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
        How to reach {vendor.name}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        {prefLabel ? (
          <span className="font-medium text-gray-900 dark:text-white">
            {prefLabel}
          </span>
        ) : null}
        {phone ? (
          <a
            href={`tel:${digits}`}
            className="text-indigo-700 hover:underline dark:text-indigo-400"
          >
            {phone}
          </a>
        ) : null}
        {email ? (
          <a
            href={`mailto:${email}`}
            className="text-indigo-700 hover:underline dark:text-indigo-400"
          >
            {email}
          </a>
        ) : null}
      </div>
      {notes ? (
        <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">{notes}</p>
      ) : null}
    </div>
  )
}
