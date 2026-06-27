import { CheckCircleIcon, ChevronRightIcon } from '@heroicons/react/20/solid'

import type { WorkOrderDetail } from '@/lib/api/types'

import { deriveStages } from './WorkflowChecklist'

/** Short labels for the horizontal strip — the full checklist keeps the
 *  long ones. Keyed by the canonical stage labels from `deriveStages`. */
const SHORT_LABELS: Record<string, string> = {
  Accepted: 'Accepted',
  'Dispatch confirmed': 'Dispatched',
  'Sub-vendor assigned': 'Assigned',
  'Vendor notified': 'Notified',
  'Vendor on-site': 'On-site',
  'Work complete': 'Complete',
  'Closed by store': 'Store-confirmed',
  'Ready to invoice': 'Ready',
  'Markup decided': 'Markup',
  Invoiced: 'Invoiced',
  Paid: 'Paid',
}

/**
 * Compact, always-visible horizontal pipeline strip. Shows every stage at
 * a glance with the current (first incomplete) one highlighted, so the
 * operator sees where the WO sits without expanding the full checklist.
 * Purely informational — actions live in the next-step hero and the
 * collapsible full checklist below.
 */
export function WorkflowStepper({ wo }: { wo: WorkOrderDetail }) {
  const stages = deriveStages(wo)
  // "Current" = the earliest stage still pending (not the un-tracked
  // on-site stage). Mirrors how the next-step card picks the next action.
  const currentIdx = stages.findIndex((s) => s.state === 'pending')

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-1.5 text-xs">
      {stages.map((stage, i) => {
        const label = SHORT_LABELS[stage.label] ?? stage.label
        const done = stage.state === 'done'
        const isCurrent = i === currentIdx
        return (
          <span key={stage.label} className="flex items-center gap-1">
            <span
              className={
                isCurrent
                  ? 'inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300'
                  : done
                    ? 'inline-flex items-center gap-1 text-gray-700 dark:text-gray-200'
                    : 'inline-flex items-center gap-1 text-gray-400 dark:text-gray-500'
              }
            >
              {done ? (
                <CheckCircleIcon className="size-3.5 text-green-600 dark:text-green-400" />
              ) : null}
              {label}
            </span>
            {i < stages.length - 1 ? (
              <ChevronRightIcon className="size-3.5 shrink-0 text-gray-300 dark:text-gray-600" />
            ) : null}
          </span>
        )
      })}
    </div>
  )
}
