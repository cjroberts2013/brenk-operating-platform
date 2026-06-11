import type { WorkOrderDetail } from '@/lib/api/types'

/**
 * Derives the single "what do I do next" step for a work order from its
 * SC status + Brenk-internal milestones. Drives the Next-step card so
 * the operator doesn't have to read the whole 10-stage checklist to
 * know the next action.
 *
 * `owner` says who acts: 'brenk' (an action in this dashboard),
 * 'sc' (something Daryl does in ServiceChannel), or 'none' (waiting /
 * complete, no action needed).
 *
 * Status semantics mirror the backend's `app/services/pipeline.py`
 * `classify()` — primary + extended together form the real state:
 * COMPLETED/CANCELED and COMPLETED/NO CHARGE are terminal,
 * COMPLETED/PENDING CONFIRMATION is still awaiting the store, and
 * IN PROGRESS/WAITING FOR APPROVAL is pre-acceptance just like OPEN.
 */

export type NextStepKind =
  | 'accept'
  | 'assign'
  | 'notify'
  | 'await-work'
  | 'await-store'
  | 'markup'
  | 'invoice'
  | 'paid'
  | 'done'
  | 'canceled'

export type NextStep = {
  kind: NextStepKind
  owner: 'brenk' | 'sc' | 'none'
  title: string
  detail: string
}

/** Kinds where the billing work (markup helper card) is the relevant
 *  surface — used to auto-expand it on the WO detail page. */
export const BILLING_STEP_KINDS: ReadonlySet<NextStepKind> = new Set([
  'markup',
  'invoice',
  'paid',
])

export function deriveNextStep(wo: WorkOrderDetail): NextStep {
  const p = (wo.primary_status || '').toUpperCase()
  const e = (wo.extended_status || '').toUpperCase()
  const completed = p.includes('COMPLETED')
  const canceled = completed && (e === 'CANCELED' || e === 'NO CHARGE')
  const awaitingStore = completed && e === 'PENDING CONFIRMATION'
  const pendingAcceptance =
    p === 'OPEN' || (p === 'IN PROGRESS' && e === 'WAITING FOR APPROVAL')
  const invoiced = wo.is_invoiced || p === 'INVOICED'
  const hasVendor = wo.assigned_vendor !== null
  const notified = Boolean(wo.brenk_vendor_notified_at)
  const hasMarkup = wo.brenk_markup_percent !== null
  const paid = Boolean(wo.brenk_paid_at)

  if (canceled) {
    return {
      kind: 'canceled',
      owner: 'none',
      title: e === 'NO CHARGE' ? 'Closed — no charge' : 'Canceled',
      detail:
        'This work order is terminal in ServiceChannel. Nothing to bill, nothing to do.',
    }
  }
  if (paid) {
    return {
      kind: 'done',
      owner: 'none',
      title: 'All done',
      detail: 'The client has paid Brenk. Nothing left to do on this one.',
    }
  }
  if (invoiced) {
    return {
      kind: 'paid',
      owner: 'brenk',
      title: 'Mark paid when the client pays',
      detail:
        'Invoiced in ServiceChannel. Mark it paid here once Brenk receives payment.',
    }
  }
  if (awaitingStore) {
    return {
      kind: 'await-store',
      owner: 'none',
      title: 'Waiting on the store to confirm',
      detail: hasMarkup
        ? 'Markup is set. Once the store confirms completion, invoice in ServiceChannel.'
        : 'Work is reported complete. Once the store confirms, price it and invoice.',
    }
  }
  if (hasMarkup) {
    return {
      kind: 'invoice',
      owner: 'sc',
      title: 'Invoice in ServiceChannel',
      detail:
        'Markup is set. Enter the total bill into SC’s invoice form to bill the client.',
    }
  }
  if (completed) {
    return {
      kind: 'markup',
      owner: 'brenk',
      title: 'Set the markup and bill',
      detail:
        'Work is complete and store-confirmed. Enter the vendor cost and markup below, then invoice.',
    }
  }
  if (pendingAcceptance) {
    return {
      kind: 'accept',
      owner: 'sc',
      title: 'Accept the work order in ServiceChannel',
      detail: 'This WO is awaiting your accept/decline in SC.',
    }
  }
  if (!hasVendor) {
    return {
      kind: 'assign',
      owner: 'brenk',
      title: 'Assign a sub-vendor',
      detail: 'Pick the sub-vendor who will do this job.',
    }
  }
  if (!notified) {
    return {
      kind: 'notify',
      owner: 'brenk',
      title: 'Notify the vendor',
      detail: `Text or call ${wo.assigned_vendor?.name ?? 'the vendor'}, then mark them notified.`,
    }
  }
  return {
    kind: 'await-work',
    owner: 'none',
    title: 'Waiting on the vendor',
    detail:
      'Vendor notified. Waiting for the work to be completed and the store to close it out.',
  }
}
