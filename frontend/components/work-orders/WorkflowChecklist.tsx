/**
 * Workflow checklist — derives the stage states for a work order.
 *
 * SC-owned stages derive from primary + extended status; Brenk-internal
 * stages (sub-vendor assigned, vendor notified, markup decided, paid)
 * derive from the Brenk columns on the WO. The only stage with no data
 * source is "Vendor on-site" (CubeSmart app GPS — no signal to us until
 * the SC Workforce token is unblocked).
 */

import type { ReactNode } from 'react'

import {
  CheckCircleIcon as CheckCircleSolid,
} from '@heroicons/react/24/solid'
import {
  CheckCircleIcon,
  MinusCircleIcon,
} from '@heroicons/react/24/outline'

import type { WorkOrderDetail } from '@/lib/api/types'

type StageState = 'done' | 'pending' | 'not_tracked'

type Stage = {
  label: string
  source: 'SC' | 'Brenk'
  state: StageState
  detail?: string
}

/** Stage labels that the parent can replace with custom interactive
 * UI (e.g. the vendor-assignment dropdown). Listed centrally so a
 * typo in a label string doesn't silently break the slot wiring. */
const SUB_VENDOR_STAGE_LABEL = 'Sub-vendor assigned'
const VENDOR_NOTIFIED_STAGE_LABEL = 'Vendor notified'

function isCompleted(status: string): boolean {
  return status.toUpperCase().includes('COMPLETED')
}

function isInProgress(status: string): boolean {
  return status.toUpperCase().includes('PROGRESS')
}

function isOpen(status: string): boolean {
  return status.toUpperCase() === 'OPEN'
}

export function deriveStages(wo: WorkOrderDetail): Stage[] {
  const status = wo.primary_status
  const extended = (wo.extended_status ?? '').toUpperCase()
  const invoiced = wo.is_invoiced || status.toUpperCase() === 'INVOICED'
  // An invoiced WO has necessarily passed every SC stage before it,
  // even though SC's primary status no longer says COMPLETED.
  const completed = isCompleted(status) || invoiced
  const storeConfirmed =
    (isCompleted(status) && extended.includes('CONFIRM')) || invoiced
  // Same definition as the backend's ready_to_invoice stage: completed
  // and past PENDING CONFIRMATION (terminal CANCELED / NO CHARGE WOs
  // shouldn't reach this card's happy path, but exclude them anyway).
  const readyToInvoice =
    (isCompleted(status) &&
      !['PENDING CONFIRMATION', 'CANCELED', 'NO CHARGE'].includes(extended)) ||
    invoiced
  const hasMarkup = wo.brenk_markup_percent !== null

  return [
    {
      label: 'Accepted',
      source: 'SC',
      state: isOpen(status) ? 'pending' : 'done',
    },
    {
      label: 'Dispatch confirmed',
      source: 'SC',
      state: isInProgress(status) || completed ? 'done' : 'pending',
    },
    {
      label: 'Sub-vendor assigned',
      source: 'Brenk',
      state: wo.assigned_vendor ? 'done' : 'pending',
      detail: wo.assigned_vendor?.name ?? 'Unassigned',
    },
    {
      label: 'Vendor notified',
      source: 'Brenk',
      state: wo.brenk_vendor_notified_at ? 'done' : 'pending',
      detail: wo.brenk_vendor_notified_at
        ? undefined
        : 'Mark when you’ve texted/called the vendor',
    },
    {
      label: 'Vendor on-site',
      source: 'Brenk',
      state: 'not_tracked',
      detail: 'CubeSmart app data — no signal to us',
    },
    {
      label: 'Work complete',
      source: 'SC',
      state: completed ? 'done' : 'pending',
    },
    {
      label: 'Closed by store',
      source: 'SC',
      state: storeConfirmed ? 'done' : 'pending',
    },
    {
      label: 'Ready to invoice',
      source: 'SC',
      state: readyToInvoice ? 'done' : 'pending',
      detail: readyToInvoice ? undefined : 'Store confirmation moves it here',
    },
    {
      label: 'Markup decided',
      source: 'Brenk',
      state: hasMarkup ? 'done' : 'pending',
      detail: hasMarkup
        ? `${Number(wo.brenk_markup_percent).toFixed(0)}% markup`
        : 'Set in the markup helper below',
    },
    { label: 'Invoiced', source: 'SC', state: invoiced ? 'done' : 'pending' },
    {
      label: 'Paid',
      source: 'Brenk',
      state: wo.brenk_paid_at ? 'done' : 'pending',
      detail: wo.brenk_paid_at
        ? undefined
        : 'Mark when the client pays Brenk',
    },
  ]
}

function StageIcon({ state }: { state: StageState }) {
  if (state === 'done')
    return (
      <CheckCircleSolid
        aria-hidden="true"
        className="size-5 shrink-0 text-green-600 dark:text-green-400"
      />
    )
  if (state === 'pending')
    return (
      <CheckCircleIcon
        aria-hidden="true"
        className="size-5 shrink-0 text-gray-300 dark:text-gray-600"
      />
    )
  return (
    <MinusCircleIcon
      aria-hidden="true"
      className="size-5 shrink-0 text-gray-300 dark:text-gray-600"
    />
  )
}

export function WorkflowChecklist({
  wo,
  vendorControl,
  notifyControl,
}: {
  wo: WorkOrderDetail
  /** Optional interactive widget rendered in the "Sub-vendor assigned"
   * row. When present, replaces the row's detail text. */
  vendorControl?: ReactNode
  /** Optional interactive widget rendered in the "Vendor notified"
   * row. When present, replaces the row's detail text. */
  notifyControl?: ReactNode
}) {
  const stages = deriveStages(wo)

  return (
    <div className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Workflow
        </h2>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          Pipeline stages — green = done, gray = pending or not yet tracked.
        </p>
      </header>
      <ul role="list" className="divide-y divide-gray-200 dark:divide-white/10">
        {stages.map((stage) => {
          const isVendorStage =
            stage.label === SUB_VENDOR_STAGE_LABEL && vendorControl
          const isNotifiedStage =
            stage.label === VENDOR_NOTIFIED_STAGE_LABEL && notifyControl
          const control = isVendorStage
            ? vendorControl
            : isNotifiedStage
              ? notifyControl
              : null
          return (
            <li
              key={stage.label}
              className="flex items-start gap-3 px-4 py-2.5 text-sm"
            >
              <StageIcon state={stage.state} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={
                      stage.state === 'done'
                        ? 'font-medium text-gray-900 dark:text-white'
                        : 'text-gray-500 dark:text-gray-400'
                    }
                  >
                    {stage.label}
                  </span>
                  <span className="rounded-sm bg-gray-100 px-1.5 py-px text-[10px] font-medium text-gray-500 uppercase dark:bg-white/5 dark:text-gray-400">
                    {stage.source}
                  </span>
                </div>
                {control ? (
                  <div className="mt-1">{control}</div>
                ) : stage.detail ? (
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {stage.detail}
                  </p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
