import Link from 'next/link'
import { notFound } from 'next/navigation'

import { ArrowLeftIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/20/solid'

import { NotesTimeline } from '@/components/work-orders/NotesTimeline'
import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { MarkupHelper } from '@/components/work-orders/MarkupHelper'
import { NextStepCard } from '@/components/work-orders/NextStepCard'
import { VendorAssignmentControl } from '@/components/work-orders/VendorAssignmentControl'
import { VendorNotifiedControl } from '@/components/work-orders/VendorNotifiedControl'
import { WorkflowChecklist } from '@/components/work-orders/WorkflowChecklist'
import { ApiError } from '@/lib/api/server'
import { listVendors } from '@/lib/api/vendors'
import {
  getWorkOrder,
  listWorkOrderNotes,
} from '@/lib/api/work-orders'
import { money, relativeTime, shortDate } from '@/lib/format'

const SC_WEB_URL =
  process.env.NEXT_PUBLIC_SC_WEB_URL?.replace(/\/$/, '') ??
  'https://sb2.servicechannel.com'

export default async function WorkOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: idStr } = await params
  const id = Number(idStr)
  if (!Number.isFinite(id) || id < 1) notFound()

  // Fetch WO + notes + active vendors in parallel. If the WO doesn't
  // exist the backend returns 404 on `getWorkOrder`; trigger Next's
  // notFound() so the framework serves its 404 page instead of bubbling
  // an unhandled error. The vendor list is best-effort — if it fails,
  // we still render the WO and just show "Unassigned" without a
  // dropdown.
  let wo
  let notes
  let activeVendors
  try {
    ;[wo, notes, activeVendors] = await Promise.all([
      getWorkOrder(id),
      listWorkOrderNotes(id),
      listVendors({ is_active: true, page_size: 200 }),
    ])
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }

  const locationLine = [wo.location?.store_id, wo.location?.name]
    .filter(Boolean)
    .join(' — ')

  // Markup helper is only relevant once a WO is at/after "work complete"
  // (or already has markup), and before it's paid. Auto-expand it then;
  // keep it collapsed otherwise so it isn't clutter on early-stage WOs.
  const p = (wo.primary_status || '').toUpperCase()
  const markupOpen =
    !wo.brenk_paid_at &&
    (p.includes('COMPLETED') ||
      p.includes('INVOICED') ||
      wo.is_invoiced ||
      wo.brenk_markup_percent !== null)

  // Full record for the assigned vendor (the WO only embeds id/name),
  // so the next-step card can show their preferred contact method.
  const assignedVendor = wo.assigned_vendor
    ? (activeVendors.items.find((v) => v.id === wo.assigned_vendor!.id) ?? null)
    : null

  return (
    <div className="space-y-6">
      <Link
        href="/work-orders"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ArrowLeftIcon className="size-4" />
        Back to Work Orders
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <StatusBadge
            status={wo.primary_status}
            extended={wo.extended_status}
          />
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Work Order #{wo.sc_number}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {wo.client?.name ?? 'Unknown client'}
            {locationLine ? <> · {locationLine}</> : null}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              NTE
            </p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">
              {money(wo.nte, wo.currency_code || 'USD')}
            </p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left + middle: WO info and notes */}
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
            <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                Details
              </h2>
            </header>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 py-4 text-sm sm:grid-cols-2">
              <Field label="Trade" value={wo.trade?.name} />
              <Field label="Priority" value={wo.priority} />
              <Field label="Category" value={wo.category} />
              <Field label="Problem code" value={wo.problem_code} />
              <Field label="Caller" value={wo.caller} />
              <Field label="Approval code" value={wo.approval_code} />
              <Field label="Call date" value={shortDate(wo.call_date)} />
              <Field
                label="Scheduled"
                value={shortDate(wo.scheduled_date)}
              />
              <Field
                label="Expires"
                value={shortDate(wo.expiration_date)}
              />
              <Field
                label="Completed"
                value={shortDate(wo.completed_date)}
              />
              <Field
                label="SC updated"
                value={relativeTime(wo.sc_updated_date)}
              />
              <Field
                label="Last synced"
                value={relativeTime(wo.last_synced_at)}
              />
            </dl>

            {wo.description ? (
              <div className="border-t border-gray-200 px-4 py-4 dark:border-white/10">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Description
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                  {wo.description}
                </p>
              </div>
            ) : null}

            {wo.resolution ? (
              <div className="border-t border-gray-200 px-4 py-4 dark:border-white/10">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Resolution
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                  {wo.resolution}
                </p>
              </div>
            ) : null}
          </section>

          <NotesTimeline notes={notes} />
        </div>

        {/* Right rail: next step + workflow + markup + meta */}
        <div className="space-y-6">
          <NextStepCard
            wo={wo}
            scWebUrl={SC_WEB_URL}
            vendorContact={assignedVendor}
          />

          <WorkflowChecklist
            wo={wo}
            vendorControl={
              <VendorAssignmentControl
                workOrderId={wo.id}
                currentVendor={wo.assigned_vendor}
                activeVendors={activeVendors.items}
              />
            }
            notifyControl={
              <VendorNotifiedControl
                workOrderId={wo.id}
                notifiedAt={wo.brenk_vendor_notified_at}
                hasVendor={wo.assigned_vendor !== null}
              />
            }
          />

          <MarkupHelper wo={wo} defaultOpen={markupOpen} />

          <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
            <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                Open in ServiceChannel
              </h2>
            </header>
            <div className="px-4 py-3 text-sm">
              <p className="text-gray-500 dark:text-gray-400">
                For actions we don&apos;t yet support in this dashboard.
              </p>
              <a
                href={`${SC_WEB_URL}/sc/wo/Workorders/index?id=${wo.sc_work_order_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
              >
                Open WO #{wo.sc_number}
                <ArrowTopRightOnSquareIcon className="size-4" />
              </a>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </dt>
      <dd className="mt-0.5 text-gray-900 dark:text-white">{value || '—'}</dd>
    </div>
  )
}
