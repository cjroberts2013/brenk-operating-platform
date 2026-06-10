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
 */

export type NextStepKind =
  | 'accept'
  | 'assign'
  | 'notify'
  | 'await-work'
  | 'markup'
  | 'invoice'
  | 'paid'
  | 'done'

export type NextStep = {
  kind: NextStepKind
  owner: 'brenk' | 'sc' | 'none'
  title: string
  detail: string
}

export function deriveNextStep(wo: WorkOrderDetail): NextStep {
  const p = (wo.primary_status || '').toUpperCase()
  const completed = p.includes('COMPLETED')
  const open = p === 'OPEN'
  const invoiced = wo.is_invoiced || p === 'INVOICED'
  const hasVendor = wo.assigned_vendor !== null
  const notified = Boolean(wo.brenk_vendor_notified_at)
  const hasMarkup = wo.brenk_markup_percent !== null
  const paid = Boolean(wo.brenk_paid_at)

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
        'Work is complete. Enter the vendor cost and markup below, then invoice.',
    }
  }
  if (open) {
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
