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
  brenk_marked_up_at: string | null
  brenk_paid_at: string | null
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
  brenk_marked_up_at: string | null
  brenk_paid_at: string | null

  notes_count: number
  attachments_count: number

  last_synced_at: string
  created_at: string
  updated_at: string
}

export type InvoiceTab = 'ready_to_markup' | 'marked_up' | 'sent' | 'paid'

export const INVOICE_TAB_LABELS: Record<InvoiceTab, string> = {
  ready_to_markup: 'Ready to mark up',
  marked_up: 'Marked up, ready to send',
  sent: 'Sent',
  paid: 'Paid',
}

/** Per-tab helper copy, shown right under the tab nav. Plain English,
 *  written for Sue/Daryl, not engineers. Explains what's in the tab
 *  and what action moves a row to the next tab. */
export const INVOICE_TAB_HELP: Record<InvoiceTab, string> = {
  ready_to_markup:
    "Work orders the store has confirmed and that haven't been priced yet. Open a work order, enter what the vendor charged Brenk, set the markup, and it moves to “Marked up, ready to send.” These numbers stay private to Brenk — they're never sent to ServiceChannel.",
  marked_up:
    'Priced and ready to invoice in ServiceChannel. The total bill shown is Brenk\'s — only Daryl enters the final amount into SC\'s invoice form. After SC processes the invoice, the next sync will move the WO into “Sent.”',
  sent:
    'Submitted to ServiceChannel and awaiting payment. When the client pays Brenk, click “Mark paid” on the WO to move it to the Paid tab.',
  paid: 'Closed out. Kept for historical reference — every paid job, with the vendor cost + markup Brenk used.',
}

export type WorkOrderListResponse = {
  items: WorkOrderSummary[]
  total: number
  page: number
  page_size: number
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
  trade_specializations: TradeRef[]
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

  trade_specializations: TradeRef[]
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
  trade_ids?: number[]
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
  /** "now" stamps brenk_paid_at=now(); "clear" resets to null. */
  paid?: 'now' | 'clear'
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

export type DashboardPipeline = {
  stages: PipelineStage[]
  stuck: StuckWorkOrder[]
  total_open: number
  total_invoiced: number
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

