import Link from 'next/link'
import { notFound } from 'next/navigation'

import {
  ArrowLeftIcon,
  ArrowTopRightOnSquareIcon,
  ChevronRightIcon,
} from '@heroicons/react/20/solid'

import { AttachmentsSection } from '@/components/work-orders/AttachmentsSection'
import { CategoryControl } from '@/components/work-orders/CategoryControl'
import { NotesTimeline } from '@/components/work-orders/NotesTimeline'
import { DeadlineBadge } from '@/components/work-orders/DeadlineBadge'
import { StatusBadge } from '@/components/work-orders/StatusBadge'
import { MarkPaidControl } from '@/components/work-orders/MarkPaidControl'
import { MarkupHelper } from '@/components/work-orders/MarkupHelper'
import { MessageVendorCard } from '@/components/work-orders/MessageVendorCard'
import { NextStepAction } from '@/components/work-orders/NextStepAction'
import { deriveNextStep } from '@/components/work-orders/next-step'
import { ScInvoiceCard } from '@/components/work-orders/ScInvoiceCard'
import { SubmitInvoiceButton } from '@/components/work-orders/SubmitInvoiceButton'
import { VendorAssignmentControl } from '@/components/work-orders/VendorAssignmentControl'
import { VendorNotifiedControl } from '@/components/work-orders/VendorNotifiedControl'
import { VendorSuggestionPanel } from '@/components/work-orders/VendorSuggestionPanel'
import { WorkflowChecklist } from '@/components/work-orders/WorkflowChecklist'
import { WorkflowStepper } from '@/components/work-orders/WorkflowStepper'
import { ApiError } from '@/lib/api/server'
import { listVendors } from '@/lib/api/vendors'
import {
  getVendorMessage,
  getVendorSuggestions,
  getWorkOrder,
  listCategories,
  listWorkOrderAttachments,
  listWorkOrderNotes,
} from '@/lib/api/work-orders'
import type {
  VendorMessage,
  VendorSuggestionResponse,
  WorkOrderAttachment,
} from '@/lib/api/types'
import { money, relativeTime, shortDate } from '@/lib/format'

const SC_WEB_URL =
  process.env.NEXT_PUBLIC_SC_WEB_URL?.replace(/\/$/, '') ??
  'https://sb2.servicechannel.com'

// Where the "Back" link returns to, keyed by the `?from=` marker the
// linking page passes. Defaults to the Work Orders list.
const BACK_TARGETS: Record<string, { href: string; label: string }> = {
  invoices: { href: '/invoices', label: 'Back to Invoices' },
  vendors: { href: '/vendors', label: 'Back to Vendors' },
  dashboard: { href: '/', label: 'Back to Dashboard' },
}
const DEFAULT_BACK = { href: '/work-orders', label: 'Back to Work Orders' }

export default async function WorkOrderDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const { id: idStr } = await params
  const sp = await searchParams
  const fromParam = typeof sp.from === 'string' ? sp.from : undefined
  const back = (fromParam && BACK_TARGETS[fromParam]) || DEFAULT_BACK
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
  let categoryList
  try {
    ;[wo, notes, activeVendors, categoryList] = await Promise.all([
      getWorkOrder(id),
      listWorkOrderNotes(id),
      listVendors({ is_active: true, page_size: 200 }),
      listCategories(),
    ])
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound()
    throw err
  }

  // Attachments live in ServiceChannel, fetched on demand — only when the
  // WO actually has any (avoids an SC round-trip on every WO view). The
  // call is best-effort: an SC hiccup shouldn't 500 the whole page.
  let attachments: WorkOrderAttachment[] = []
  let attachmentsFailed = false
  if (wo.attachments_count > 0) {
    try {
      attachments = await listWorkOrderAttachments(wo.id)
    } catch {
      attachmentsFailed = true
    }
  }

  // Vendor message — only once a sub-vendor is assigned. Best-effort: it
  // makes a live SC call for photo names, so a hiccup just hides the card.
  let vendorMessage: VendorMessage | null = null
  if (wo.assigned_vendor) {
    try {
      vendorMessage = await getVendorMessage(wo.id)
    } catch {
      vendorMessage = null
    }
  }

  const locationLine = [wo.location?.store_id, wo.location?.name]
    .filter(Boolean)
    .join(' — ')

  // The next step drives which tool is hoisted into the action-first
  // hero vs. left collapsed in the reference rail. Same derivation as
  // the hero + workflow checklist.
  const nextStep = deriveNextStep(wo)
  // The pricing steps (set markup / invoice) put the markup helper in the
  // hero (expanded); every other step leaves it collapsed in the rail.
  // The later "mark paid" step gets its own control, not the markup tool.
  const markupInHero =
    nextStep.kind === 'markup' || nextStep.kind === 'invoice'
  // The notify step puts the vendor-message card in the hero; otherwise
  // it sits in the rail as reference.
  const notifyStep = nextStep.kind === 'notify'
  // Submit button appears exactly when the derived next step is "invoice
  // in SC": markup is set, the WO is invoice-eligible, and no active SC
  // invoice exists yet. The dialog re-validates server-side regardless.
  const canSubmitInvoice = nextStep.kind === 'invoice'

  // Vendor suggestions — fetched only at the assign step (mirrors the
  // conditional vendor-message fetch). Best-effort: a failure leaves the
  // panel to fall back to the plain dropdown.
  let vendorSuggestions: VendorSuggestionResponse | null = null
  if (nextStep.kind === 'assign') {
    try {
      vendorSuggestions = await getVendorSuggestions(wo.id)
    } catch {
      vendorSuggestions = null
    }
  }

  // Full record for the assigned vendor (the WO only embeds id/name),
  // so the next-step card can show their preferred contact method.
  const assignedVendor = wo.assigned_vendor
    ? (activeVendors.items.find((v) => v.id === wo.assigned_vendor!.id) ?? null)
    : null

  // Controls built once and placed either in the hero (current step) or
  // the rail/checklist (reference). The vendor + notify controls also
  // back the collapsible full checklist, so the operator can override any
  // stage; React renders the same element in both spots independently.
  const vendorControl = (
    <VendorAssignmentControl
      workOrderId={wo.id}
      assignments={wo.vendor_assignments}
      activeVendors={activeVendors.items}
    />
  )
  // At the assign step the hero wraps the dropdown in the suggestion panel
  // (top pick + runner-ups); elsewhere (and in the override checklist) the
  // plain dropdown is used.
  const assignControl =
    nextStep.kind === 'assign' ? (
      <VendorSuggestionPanel
        workOrderId={wo.id}
        suggestions={vendorSuggestions}
        dropdown={vendorControl}
      />
    ) : (
      vendorControl
    )
  const notifyControl = (
    <VendorNotifiedControl
      workOrderId={wo.id}
      assignments={wo.vendor_assignments}
    />
  )
  const messageCard = vendorMessage ? (
    <MessageVendorCard
      workOrderId={wo.id}
      message={vendorMessage}
      attachments={attachments}
    />
  ) : null
  const markupHelper = <MarkupHelper wo={wo} defaultOpen={markupInHero} />
  const submitButton = canSubmitInvoice ? (
    <SubmitInvoiceButton workOrderId={wo.id} />
  ) : null
  const paidControl = (
    <MarkPaidControl workOrderId={wo.id} paidAt={wo.brenk_paid_at} />
  )

  return (
    <div className="space-y-6">
      <Link
        href={back.href}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ArrowLeftIcon className="size-4" />
        {back.label}
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              status={wo.primary_status}
              extended={wo.extended_status}
            />
            <DeadlineBadge
              urgency={wo.deadline_urgency}
              daysPast={wo.deadline_days_past}
            />
          </div>
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

      {/* Always-visible pipeline strip + collapsible full checklist for
          overriding any stage. Replaces the tall vertical checklist. */}
      <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        <div className="px-4 py-3">
          <WorkflowStepper wo={wo} />
        </div>
        <details className="group border-t border-gray-200 dark:border-white/10">
          <summary className="flex cursor-pointer list-none items-center gap-1 px-4 py-2 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 [&::-webkit-details-marker]:hidden">
            <ChevronRightIcon className="size-3.5 transition-transform group-open:rotate-90" />
            All stages &amp; overrides
          </summary>
          <div className="border-t border-gray-200 dark:border-white/10">
            <WorkflowChecklist
              wo={wo}
              variant="bare"
              vendorControl={vendorControl}
              notifyControl={notifyControl}
            />
          </div>
        </details>
      </section>

      {/* The single most important thing on the page, full width at the
          top: what to do next AND the tool to do it. */}
      <NextStepAction
        wo={wo}
        scWebUrl={SC_WEB_URL}
        assignedVendor={assignedVendor}
        vendorControl={assignControl}
        notifyControl={notifyControl}
        messageCard={notifyStep ? messageCard : null}
        markupHelper={markupInHero ? markupHelper : null}
        submitButton={submitButton}
        paidControl={paidControl}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left + middle: WO info and notes */}
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
            <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                Details
              </h2>
            </header>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 py-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
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

          {wo.attachments_count > 0 || attachmentsFailed ? (
            <AttachmentsSection
              workOrderId={wo.id}
              attachments={attachments}
              failed={attachmentsFailed}
            />
          ) : null}

          <NotesTimeline notes={notes} />
        </div>

        {/* Right rail: reference cards. The active step's tool lives in
            the hero above; this rail holds the category, the SC invoice
            state, and whatever tool isn't currently in the hero. */}
        <div className="space-y-6">
          <CategoryControl
            workOrderId={wo.id}
            category={wo.brenk_category}
            source={wo.brenk_category_source}
            categories={categoryList.categories}
          />

          {/* Vendor message lives in the hero on the notify step; here as
              reference at every other stage (so it stays reachable). */}
          {messageCard && !notifyStep ? messageCard : null}

          {/* Markup helper lives (expanded) in the hero on the pricing
              steps; here collapsed as reference at every other stage. */}
          {!markupInHero ? markupHelper : null}

          <ScInvoiceCard wo={wo} scWebUrl={SC_WEB_URL} />

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
