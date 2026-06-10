import { ArrowTopRightOnSquareIcon, CheckCircleIcon } from '@heroicons/react/20/solid'

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
 * Prominent "what to do next" card at the top of the WO right rail.
 * Surfaces the single next action derived from the WO's stage so the
 * operator doesn't have to scan the whole workflow checklist.
 *
 * For SC-owned steps it links straight into ServiceChannel. For
 * Brenk-owned steps it points at the control just below (vendor
 * assignment / notify in the workflow, or the markup helper).
 */
export function NextStepCard({
  wo,
  scWebUrl,
  vendorContact,
}: {
  wo: WorkOrderDetail
  scWebUrl: string
  /** Full record for the assigned vendor, when available, so the
   *  "notify" step can show their preferred contact method. */
  vendorContact?: VendorSummary | null
}) {
  const step = deriveNextStep(wo)
  const done = step.kind === 'done'
  const waiting = step.owner === 'none' && !done

  // Indigo accent when there's an action to take; muted when waiting/done.
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

  return (
    <section className={`rounded-lg p-4 ring-1 ${tone}`}>
      <div className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${eyebrow}`}>
        {done ? <CheckCircleIcon className="size-4" /> : null}
        {done ? 'Complete' : waiting ? 'Status' : 'Next step'}
      </div>
      <h2 className="mt-1.5 text-base font-semibold text-gray-900 dark:text-white">
        {step.title}
      </h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
        {step.detail}
      </p>

      {step.kind === 'notify' && vendorContact ? (
        <NotifyContact vendor={vendorContact} />
      ) : null}

      {step.owner === 'sc' ? (
        <a
          href={`${scWebUrl}/sc/wo/Workorders/index?id=${wo.sc_work_order_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Open in ServiceChannel
          <ArrowTopRightOnSquareIcon className="size-4" />
        </a>
      ) : null}
    </section>
  )
}

/** Preferred-contact block shown on the "notify" step so Daryl can
 *  reach the assigned vendor the way they like, in one tap. */
function NotifyContact({ vendor }: { vendor: VendorSummary }) {
  const prefLabel = preferredContactLabel(vendor.contact_preference)
  const { phone, email, communication_notes: notes } = vendor
  const digits = phone ? phone.replace(/\D/g, '') : ''
  if (!prefLabel && !phone && !email && !notes) return null
  return (
    <div className="mt-3 rounded-md bg-white/70 px-3 py-2 dark:bg-white/5">
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
