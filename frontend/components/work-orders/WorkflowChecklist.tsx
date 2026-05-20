/**
 * Workflow checklist — derives the stage states for a work order.
 *
 * Stages that can be derived from SC data today show real status.
 * Brenk-internal stages (vendor texted, ready to invoice, markup
 * decided, etc.) show as "Not tracked yet" placeholders until the
 * vendor model and invoice queue ship.
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
  const extended = wo.extended_status ?? ''

  const accepted: StageState = isOpen(status) ? 'pending' : 'done'
  const dispatchConfirmed: StageState =
    isInProgress(status) || isCompleted(status) || wo.is_invoiced
      ? 'done'
      : 'pending'

  const subVendor: StageState = wo.assigned_vendor ? 'done' : 'not_tracked'

  const workComplete: StageState = isCompleted(status) ? 'done' : 'pending'
  const storeConfirmed: StageState =
    isCompleted(status) && extended.toUpperCase().includes('CONFIRM')
      ? 'done'
      : 'pending'

  const invoiced: StageState = wo.is_invoiced ? 'done' : 'pending'

  return [
    { label: 'Accepted', source: 'SC', state: accepted },
    { label: 'Dispatch confirmed', source: 'SC', state: dispatchConfirmed },
    {
      label: 'Sub-vendor assigned',
      source: 'Brenk',
      state: subVendor,
      detail:
        wo.assigned_vendor?.name ??
        (subVendor === 'not_tracked'
          ? 'Vendors page lands next'
          : 'Unassigned'),
    },
    {
      label: 'Vendor notified',
      source: 'Brenk',
      state: 'not_tracked',
      detail: 'Texting tracker lands in Phase 3',
    },
    {
      label: 'Vendor on-site',
      source: 'Brenk',
      state: 'not_tracked',
      detail: 'CubeSmart app data — no signal to us',
    },
    { label: 'Work complete', source: 'SC', state: workComplete },
    { label: 'Closed by store', source: 'SC', state: storeConfirmed },
    {
      label: 'Ready to invoice',
      source: 'Brenk',
      state: 'not_tracked',
      detail: 'Invoice queue lands next',
    },
    {
      label: 'Markup decided',
      source: 'Brenk',
      state: 'not_tracked',
      detail: 'Invoice queue lands next',
    },
    { label: 'Invoiced', source: 'SC', state: invoiced },
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
}: {
  wo: WorkOrderDetail
  /** Optional interactive widget rendered in the "Sub-vendor assigned"
   * row. When present, replaces the row's detail text. */
  vendorControl?: ReactNode
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
          return (
            <li
              key={stage.label}
              className="flex items-start gap-3 px-4 py-2.5 text-sm"
            >
              <StageIcon
                state={
                  // When the vendor control is present and the WO has
                  // someone assigned, mark this stage done regardless of
                  // what the static deriveStages logic returned.
                  isVendorStage && wo.assigned_vendor ? 'done' : stage.state
                }
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={
                      stage.state === 'done' ||
                      (isVendorStage && wo.assigned_vendor)
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
                {isVendorStage ? (
                  <div className="mt-1">{vendorControl}</div>
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
