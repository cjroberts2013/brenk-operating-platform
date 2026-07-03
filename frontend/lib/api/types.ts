/**
 * TypeScript mirrors of the backend Pydantic schemas in
 * `backend/app/schemas/work_order.py`.
 *
 * Hand-written for now. If the backend schemas ever drift from these,
 * the easiest fix is to regenerate from FastAPI's `/openapi.json`
 * using openapi-typescript or similar — TODO when the shapes settle.
 */

export type ClientRef = {
  id: number
  sc_subscriber_id: number
  name: string
  short_name: string | null
}

export type LocationRef = {
  id: number
  sc_location_id: number
  store_id: string | null
  name: string | null
}

export type TradeRef = {
  id: number
  sc_trade_id: number | null
  name: string
  default_markup_percent: string | null // serialized Decimal
}

export type VendorRef = {
  id: number
  sc_provider_id: number | null
  name: string
}

export type AssignedVendor = {
  vendor: VendorRef
  job_type: JobType | null
  notified_at: string | null
  labor_cost: string | null
  material_cost: string | null
  paid_to_vendor_at: string | null
}

export type WorkOrderSummary = {
  id: number
  sc_work_order_id: number
  sc_number: string
  primary_status: string
  extended_status: string | null
  priority: string | null
  trade: TradeRef | null
  location: LocationRef | null
  client: ClientRef | null
  assigned_vendor: VendorRef | null
  vendor_assignments: AssignedVendor[]
  nte: string | null // serialized as a decimal string by FastAPI
  scheduled_date: string | null // ISO 8601
  sc_updated_date: string | null // ISO 8601
  // Brenk-invoice fields — surfaced on the list so the invoice
  // queue tabs can render vendor cost + markup + paid inline.
  // Labor + material are what Brenk pays the sub-vendor, split for
  // analytics (Phase 4 wants to see where the money's going).
  // Total vendor cost = labor + material. NEVER auto-derived from
  // NTE — those are different numbers. Brenk-confidential.
  brenk_labor_cost: string | null
  brenk_material_cost: string | null
  brenk_markup_percent: string | null
  /** Directly-entered pre-tax total bill — set when Daryl prices by the
   *  total instead of vendor cost + markup. When set, it's the total
   *  source of truth and the markup % is unknown. Brenk-confidential. */
  brenk_total_override: string | null
  brenk_marked_up_at: string | null
  brenk_paid_at: string | null
  brenk_vendor_notified_at: string | null
  /** Brenk job category (curated taxonomy — distinct from the SC `trade`).
   *  `source`: 'ai' = Gemini-suggested, unreviewed; 'confirmed' = operator
   *  accepted the AI guess; 'manual' = operator set/changed it. `confidence`
   *  is Gemini's 0–1 score (decimal string), only meaningful for 'ai'. */
  brenk_category: string | null
  brenk_category_source: string | null // 'ai' | 'confirmed' | 'manual'
  brenk_category_confidence: string | null
  /** Computed by the list endpoint: WO is past its stage's stuck
   *  threshold (same definition the dashboard uses). */
  is_stuck: boolean
  /** Turnaround deadline, computed by the backend (scheduled_date, else
   *  call_date + 5d) — same definitions as the `?deadline=` filter and
   *  the dashboard's Deadline watch. All null once work is complete.
   *  `deadline_days_past` is signed: positive = overdue. */
  deadline_date: string | null // ISO 8601
  deadline_urgency: DeadlineUrgency | null
  deadline_days_past: number | null
  // SC invoice state synced from webhooks (for the post-submit tabs).
  sc_invoice_number: string | null
  sc_invoice_status: string | null
  sc_invoice_total: string | null
  sc_invoice_submitted_at: string | null
  sc_invoice_last_error: string | null
  sc_paid_at: string | null
}

/** A ServiceChannel invoice record, synced from SC invoice webhooks. */
export type InvoiceSummary = {
  sc_invoice_id: number | null
  invoice_number: string
  status: string | null
  currency: string | null
  subtotal: string | null
  invoice_tax: string | null
  invoice_total: string | null
  approval_code: string | null
  batch_number: string | null
  comments: string | null
  trade: string | null
  category: string | null
  invoice_date: string | null
  posted_date: string | null
  approved_date: string | null
  paid_date: string | null
  last_action_date: string | null
  sc_updated_date: string | null
  source: string
}

/** An actual SC invoice plus its linked work order (for the invoice list). */
export type InvoiceListItem = InvoiceSummary & {
  work_order_id: number | null
  wo_number: string | null
  location_name: string | null
  location_store_id: string | null
}

export type InvoiceListResponse = {
  items: InvoiceListItem[]
  total: number
  page: number
  page_size: number
}

/** Server-computed preview of what submitting a WO's invoice to SC
 *  would send — rendered verbatim in the confirm dialog. */
export type InvoiceSubmitPreview = {
  eligible: boolean
  problems: string[]
  invoice_number: string
  labor_amount: string
  material_amount: string
  subtotal: string
  /** 8.25% TX sales tax on the marked-up subtotal. */
  tax_amount: string
  /** subtotal + tax; checked against NTE. */
  invoice_total: string
  nte: string | null
  resolution_text: string | null
}

export type WorkOrderDetail = {
  id: number
  sc_work_order_id: number
  sc_number: string
  sc_purchase_number: string | null

  client: ClientRef | null
  location: LocationRef | null
  trade: TradeRef | null
  assigned_vendor: VendorRef | null
  vendor_assignments: AssignedVendor[]

  primary_status: string
  extended_status: string | null
  can_create_invoice: boolean

  category: string | null
  sc_category_id: number | null
  priority: string | null
  problem_code: string | null

  description: string | null
  resolution: string | null
  caller: string | null
  approval_code: string | null

  nte: string | null
  currency_code: string

  call_date: string | null
  scheduled_date: string | null
  expiration_date: string | null
  original_eta: string | null
  sc_updated_date: string | null
  completed_date: string | null

  is_invoiced: boolean
  is_expired: boolean
  is_check_in_denied: boolean
  has_work_activity: boolean
  auto_complete: boolean
  auto_invoice: boolean

  // Brenk-confidential — never pushed to SC. See backend model
  // docstring for the full privacy boundary.
  brenk_labor_cost: string | null
  brenk_material_cost: string | null
  brenk_markup_percent: string | null
  /** Directly-entered pre-tax total bill. When set, it's the total
   *  source of truth and the markup % is unknown. Brenk-confidential. */
  brenk_total_override: string | null
  brenk_marked_up_at: string | null
  brenk_paid_at: string | null
  brenk_vendor_notified_at: string | null

  // Brenk job category (AI-inferred, operator-confirmed/overridden).
  brenk_category: string | null
  brenk_category_source: string | null // 'ai' | 'confirmed' | 'manual'
  brenk_category_confidence: string | null
  brenk_category_ai: string | null
  brenk_category_at: string | null
  /** Computed markup suggestion: category average (≥3 jobs) else trade
   *  default. `*_label` explains the basis. */
  suggested_markup_percent: string | null
  suggested_markup_label: string | null

  /** Turnaround deadline — same computed fields as WorkOrderSummary. */
  deadline_date: string | null // ISO 8601
  deadline_urgency: DeadlineUrgency | null
  deadline_days_past: number | null

  // ServiceChannel invoice state, synced from SC invoice webhooks.
  sc_invoice_id: number | null
  sc_invoice_number: string | null
  sc_invoice_status: string | null
  sc_invoice_total: string | null
  sc_invoice_submitted_at: string | null
  sc_invoice_last_error: string | null
  sc_paid_at: string | null
  /** Full linked SC invoice record(s), latest first. */
  sc_invoices: InvoiceSummary[]

  notes_count: number
  attachments_count: number

  last_synced_at: string
  created_at: string
  updated_at: string
}

/** Backend-computed turnaround urgency (`app/services/deadlines.py`). */
export type DeadlineUrgency = 'overdue' | 'due_soon' | 'ok'

/** `?deadline=` filter vocabulary. at_risk = overdue + due_soon. */
export type DeadlineFilterKey = 'at_risk' | 'overdue' | 'due_soon'

export const DEADLINE_FILTER_LABELS: Record<DeadlineFilterKey, string> = {
  at_risk: 'At-risk turnaround',
  overdue: 'Past turnaround deadline',
  due_soon: 'Turnaround due soon',
}

export type InvoiceTab =
  | 'ready_to_markup'
  | 'marked_up'
  | 'sent'
  | 'rejected'
  | 'paid'

export const INVOICE_TAB_LABELS: Record<InvoiceTab, string> = {
  ready_to_markup: 'Ready to mark up',
  marked_up: 'Marked up, ready to send',
  sent: 'Sent',
  rejected: 'Rejected',
  paid: 'Paid',
}

/** Per-tab helper copy, shown right under the tab nav. Plain English,
 *  written for Sue/Daryl, not engineers. Explains what's in the tab
 *  and what action moves a row to the next tab. */
export const INVOICE_TAB_HELP: Record<InvoiceTab, string> = {
  ready_to_markup:
    "Work orders the store has confirmed and that haven't been priced yet. Open a work order, enter what the vendor charged Brenk, set the markup, and it moves to “Marked up, ready to send.” These numbers stay private to Brenk; they're never sent to ServiceChannel.",
  marked_up:
    "Priced and ready to invoice in ServiceChannel. The total bill shown is Brenk's; only Daryl enters the final amount into SC's invoice form. Once the invoice appears in SC, the webhook moves the WO into “Sent” on its own.",
  sent: 'Submitted to ServiceChannel and awaiting payment, synced live from SC. When SC marks it paid (or you Mark paid on the WO), it moves to the Paid tab.',
  rejected:
    'ServiceChannel rejected the invoice. Open the WO to see the reason, fix it, and resubmit in SC; the webhook updates the status from there.',
  paid: 'Closed out. Kept for reference: every paid job, with the SC invoice plus the vendor cost + markup Brenk used.',
}

export type WorkOrderListResponse = {
  items: WorkOrderSummary[]
  total: number
  page: number
  page_size: number
}

/** A ready-to-send vendor notification message for a work order. `body`
 *  pastes into SMS or email; `subject` is the suggested email subject. */
export type VendorMessage = {
  subject: string
  body: string
  to_phone: string | null
  to_email: string | null
  contact_preference: string | null
  photo_count: number
}

/** A file attached to a work order (from SC's OData attachments list).
 *  The raw SC presigned `Uri` is never exposed — downloads go through our
 *  proxy. `content_type` is guessed from the file name. */
export type WorkOrderAttachment = {
  id: number
  name: string | null
  description: string | null
  note_id: number | null
  timestamp: string | null // ISO 8601
  is_invoice_digital_copy: boolean
  upload_by: string | null
  content_type: string | null
}

export type WorkOrderNoteRef = {
  id: number
  sc_note_id: number | null
  note_number: number | null
  note_data: string
  note_type: string | null
  action_required: boolean
  is_pinned: boolean
  is_attachment_note: boolean
  created_by: string | null
  company_name: string | null
  created_at_sc: string | null
  source: string
}

/** Pipeline-funnel stage keys. Mirrors the backend's
 *  `app/services/pipeline.py` STAGES tuple. Tile clicks from the
 *  dashboard land on the WO list page with `?stage=…`. */
export type PipelineStageKey =
  | 'pending_acceptance'
  | 'dispatched'
  | 'work_complete'
  | 'ready_to_invoice'
  | 'invoiced'

/** Human-readable labels for each stage key, used by the filter chip
 *  on the WO list page. Kept in sync with the labels the dashboard
 *  endpoint emits — same text in both places. */
export const STAGE_LABELS: Record<PipelineStageKey, string> = {
  pending_acceptance: 'Pending acceptance',
  dispatched: 'Dispatched',
  work_complete: 'Work complete · awaiting store',
  ready_to_invoice: 'Ready to invoice',
  invoiced: 'Invoiced',
}

/** Query params accepted by `GET /api/v1/work-orders/`. */
export type WorkOrderListParams = {
  status?: string
  client_id?: number
  trade_id?: number
  assigned_vendor_id?: number
  updated_since?: string // ISO 8601
  q?: string
  stage?: PipelineStageKey
  /** Invoice-queue tab filter — same source-of-truth as the backend
   *  `app/api/v1/endpoints/work_orders.py` invoice_tab param. */
  invoice_tab?: InvoiceTab
  /** Only WOs stuck past their stage's age threshold. */
  stuck?: boolean
  /** Turnaround-deadline filter over unfinished WOs — same definitions
   *  as the dashboard's Deadline watch panel. */
  deadline?: DeadlineFilterKey
  /** Only WOs whose category is AI-suggested and not yet confirmed
   *  (brenk_category_source = 'ai'). Drives the "Needs review" toggle. */
  category_review?: boolean
  page?: number
  page_size?: number
}

export type WorkOrderSyncStatus = {
  last_synced_at: string | null // ISO 8601, UTC
  work_order_count: number
}

export type WorkOrderSyncSummary = {
  fetched: number
  upserted: number
  notes_synced: number
  errors: number
}

// =============================================================================
// Vendors
// =============================================================================

export type JobType = {
  id: number
  name: string
  description: string | null
  position: number
  is_active: boolean
  is_catchall: boolean
}

export type VendorContactPreference = 'sms' | 'call' | 'email' | 'other'

export type VendorSummary = {
  id: number
  name: string
  phone: string | null
  email: string | null
  notes: string | null
  is_active: boolean
  contact_preference: string | null
  payment_terms: string | null
  service_area: string | null
  mobile_app_capable: boolean | null
  markup_notes: string | null
  communication_notes: string | null
  active_work_orders: number
  skills: JobType[]
}

export type VendorSuggestionAxis = {
  score: number
  reason: string
}

export type VendorSuggestion = {
  vendor: VendorSummary
  composite_score: number
  trade: VendorSuggestionAxis
  location: VendorSuggestionAxis
  workload: VendorSuggestionAxis
  reason: string
  /** This vendor is already assigned to the WO (excluded from top_pick). */
  is_current: boolean
}

export type VendorSuggestionResponse = {
  /** Best non-current match, only when it clears the strong-match threshold;
   *  null → the UI degrades to the manual dropdown. */
  top_pick: VendorSuggestion | null
  ranked: VendorSuggestion[]
  has_trade: boolean
  wo_city: string | null
}

export type VendorDetail = {
  id: number
  sc_provider_id: number | null
  name: string
  phone: string | null
  email: string | null
  notes: string | null
  is_active: boolean

  contact_preference: string | null
  payment_terms: string | null
  service_area: string | null
  mobile_app_capable: boolean | null
  markup_notes: string | null
  communication_notes: string | null

  skills: JobType[]
  active_work_orders: number

  created_at: string
  updated_at: string
}

export type VendorListResponse = {
  items: VendorSummary[]
  total: number
  page: number
  page_size: number
}

export type VendorListParams = {
  is_active?: boolean
  trade_id?: number
  q?: string
  page?: number
  page_size?: number
}

/** Shape of the body for POST /api/v1/vendors. */
export type VendorCreate = {
  name: string
  phone?: string | null
  email?: string | null
  notes?: string | null
  is_active?: boolean
  contact_preference?: VendorContactPreference | null
  payment_terms?: string | null
  service_area?: string | null
  mobile_app_capable?: boolean | null
  markup_notes?: string | null
  communication_notes?: string | null
  job_type_ids?: number[]
}

/** Shape of the body for PATCH /api/v1/vendors/{id}. All fields optional. */
export type VendorUpdate = Partial<VendorCreate>

/** Shape of the body for PATCH /api/v1/work-orders/{id}.
 *  Omitting a field leaves the column untouched; setting to null
 *  clears it (except `paid`, which uses the "now" / "clear" strings). */
export type WorkOrderUpdate = {
  assigned_vendor_id?: number | null
  /** Decimal as string. Labor portion of what Brenk pays the
   *  sub-vendor. Brenk-confidential. Null clears. */
  brenk_labor_cost?: string | null
  /** Decimal as string. Materials portion of what Brenk pays the
   *  sub-vendor. Brenk-confidential. Null clears. */
  brenk_material_cost?: string | null
  /** Decimal as string. Setting auto-stamps brenk_marked_up_at on
   *  first set; subsequent edits don't bump it. Null clears both. */
  brenk_markup_percent?: string | null
  /** Decimal as string. Directly-entered pre-tax total bill (prices the
   *  WO without a vendor cost/markup breakdown). Setting it counts as
   *  "priced" for brenk_marked_up_at. Null clears. Brenk-confidential. */
  brenk_total_override?: string | null
  /** "now" stamps brenk_paid_at=now(); "clear" resets to null. */
  paid?: 'now' | 'clear'
  /** "now" stamps brenk_vendor_notified_at=now() (Daryl texted/called
   *  the assigned sub-vendor); "clear" resets to null. */
  notified?: 'now' | 'clear'
  /** Manual category override (must be in the taxonomy → source 'manual').
   *  Null clears. */
  brenk_category?: string | null
  /** "confirm" marks the current AI category operator-confirmed. */
  category_action?: 'confirm'
}

/** Shape of the body for PATCH /api/v1/trades/{id}. */
export type TradeUpdate = {
  default_markup_percent?: string | null
}

// =============================================================================
// Dashboard
// =============================================================================

export type PipelineStageColor =
  | 'pink'
  | 'yellow'
  | 'orange'
  | 'green'
  | 'emerald'
  | 'gray'

export type PipelineStageIcon = 'user' | 'chat' | 'money' | 'check' | null

export type PipelineStage = {
  key: string
  label: string
  color: PipelineStageColor
  icon: PipelineStageIcon
  count: number
  avg_age_days: number | null
  stuck_count: number
  stuck_threshold_days: number | null
}

export type StuckWorkOrder = {
  id: number
  sc_work_order_id: number
  sc_number: string
  primary_status: string
  extended_status: string | null
  stage_key: string
  stage_label: string
  age_days: number
  overdue_by_days: number
  trade: TradeRef | null
  location: LocationRef | null
  assigned_vendor: VendorRef | null
  nte: string | null
  scheduled_date: string | null
  sc_updated_date: string | null
}

/** Dashboard dollar totals. Amounts are 2-dp decimal strings, same as
 *  the WO money fields. Mirrors `app/services/money.py` MoneyStats. */
export type MoneyStats = {
  unbilled_priced_total: string
  unbilled_priced_count: number
  unbilled_unpriced_nte_total: string
  unbilled_unpriced_count: number
  awaiting_total: string
  awaiting_count: number
  awaiting_unknown_count: number
  paid_month_total: string
  paid_month_count: number
  paid_month_profit: string | null
  month_label: string
}

/** Turnaround-deadline counts for the Deadline watch panel. Counts use
 *  the same backend definitions as the `?deadline=` list filter, so a
 *  count always equals the row total of the list it links to. */
export type DeadlineWatch = {
  overdue_count: number
  due_soon_count: number
  needs_action_count: number
  waiting_on_cubesmart_count: number
  due_soon_window_days: number
}

export type DashboardPipeline = {
  stages: PipelineStage[]
  stuck: StuckWorkOrder[]
  total_open: number
  total_invoiced: number
  money: MoneyStats
  deadline_watch: DeadlineWatch
}

// =============================================================================
// Reports (markup / spend analytics)
// =============================================================================

// Money figures arrive as 2-dp strings (serialized Decimals); the UI
// formats them. Markup percents are numbers (averages, not money).

export type ReportsTotals = {
  jobs_with_markup: number
  total_vendor_cost: string
  total_margin: string
  total_billed: string
  blended_markup_percent: number | null
}

export type MarkupByTrade = {
  trade_id: number
  trade_name: string
  default_markup_percent: number | null
  jobs_with_markup: number
  avg_actual_markup_percent: number | null
  delta_percent: number | null
  total_vendor_cost: string
  total_margin: string
}

export type MarkupByCategory = {
  category: string
  jobs_with_markup: number
  avg_actual_markup_percent: number | null
  total_vendor_cost: string
  total_margin: string
}

export type CategoryOverview = {
  category: string
  jobs: number
  invoiced_jobs: number
  billed: string
  paid: string
}

export type ReportsCoverage = {
  invoiced_jobs: number
  priced_jobs: number
}

export type VendorSpend = {
  vendor_id: number
  vendor_name: string
  jobs: number
  total_vendor_cost: string
  total_margin: string
}

export type ReportsSummary = {
  totals: ReportsTotals
  markup_by_trade: MarkupByTrade[]
  markup_by_category: MarkupByCategory[]
  vendor_spend: VendorSpend[]
  category_overview: CategoryOverview[]
  coverage: ReportsCoverage | null
}

export type VendorPayable = {
  work_order_id: number
  sc_number: string
  vendor_id: number
  vendor_name: string
  location: string | null
  payout: string
  client_paid: boolean
}

export type PayablesResponse = {
  items: VendorPayable[]
  total_outstanding: string
  total_client_paid: string
}

// =============================================================================
// Storefront (Phase 5 — public marketing site + editor)
// =============================================================================

export type StorefrontServiceItem = {
  /** Set on read; ignored on write (server assigns new ids on
   *  every replace). */
  id?: number | null
  sort_order: number
  title: string
  description: string | null
  /** Heroicon outline name — the renderer maps this to the actual
   *  icon component. e.g. 'wrench-screwdriver', 'bolt'. */
  icon: string | null
}

export type Storefront = {
  id: number

  hero_title: string | null
  hero_subtitle: string | null
  hero_cta_text: string | null
  hero_cta_link: string | null
  hero_image_url: string | null

  about_heading: string | null
  about_body: string | null
  about_image_url: string | null

  service_area_heading: string | null
  service_area_body: string | null

  contact_email: string | null
  contact_phone: string | null
  contact_address: string | null
  contact_hours: string | null

  footer_tagline: string | null
  footer_copyright: string | null

  logo_url: string | null

  services: StorefrontServiceItem[]

  created_at: string
  updated_at: string
}

/** PATCH body — every field optional. Omit to leave alone; pass
 *  null to clear. */
export type StorefrontUpdate = Partial<
  Omit<Storefront, 'id' | 'services' | 'created_at' | 'updated_at'>
>

// ---------------------------------------------------------------------------
// Locations
// ---------------------------------------------------------------------------

/** 3-tier operational health flag. null = unrated. */
export type LocationRating = 'good' | 'watch' | 'problem'

/** A gate/access code with its lifecycle state. Codes are invalidated, not
 *  deleted, so history is preserved. */
export type GateCode = {
  id: number
  label: string | null
  code: string
  is_active: boolean
  invalidated_at: string | null // ISO 8601
  created_at: string
  updated_at: string
}

export type LocationSummary = {
  id: number
  sc_location_id: number
  store_id: string | null
  name: string | null
  region: string | null
  district: string | null
  rating: string | null
  district_manager_name: string | null
  total_work_orders: number
  active_work_orders: number
  last_work_order_date: string | null // ISO 8601
}

export type LocationDetail = {
  id: number
  sc_location_id: number
  store_id: string | null
  name: string | null
  region: string | null
  district: string | null
  latitude: string | null
  longitude: string | null
  district_manager_name: string | null
  district_manager_phone: string | null
  district_manager_email: string | null
  rating: string | null
  description: string | null
  /** One-line address derived from the SC raw_data blob. */
  address: string | null
  gate_codes_active: GateCode[]
  gate_codes_history: GateCode[]
  total_work_orders: number
  active_work_orders: number
  last_work_order_date: string | null
  work_orders: WorkOrderSummary[]
  created_at: string
  updated_at: string
}

export type LocationListParams = {
  q?: string
  rating?: string
  page?: number
  page_size?: number
}

export type LocationListResponse = {
  items: LocationSummary[]
  total: number
  page: number
  page_size: number
}

/** PATCH body for /api/v1/locations/{id}. Brenk enrichment fields only;
 *  every field optional. */
export type LocationUpdate = {
  district_manager_name?: string | null
  district_manager_phone?: string | null
  district_manager_email?: string | null
  rating?: LocationRating | null
  description?: string | null
}

/** POST body for adding a gate code. */
export type GateCodeCreate = {
  code: string
  label?: string | null
}

