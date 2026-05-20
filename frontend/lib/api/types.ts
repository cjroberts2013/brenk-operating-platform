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
  nte: string | null // serialized as a decimal string by FastAPI
  scheduled_date: string | null // ISO 8601
  sc_updated_date: string | null // ISO 8601
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

  notes_count: number
  attachments_count: number

  last_synced_at: string
  created_at: string
  updated_at: string
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

/** Query params accepted by `GET /api/v1/work-orders/`. */
export type WorkOrderListParams = {
  status?: string
  client_id?: number
  trade_id?: number
  assigned_vendor_id?: number
  updated_since?: string // ISO 8601
  page?: number
  page_size?: number
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
  mobile_app_capable?: boolean | null
  markup_notes?: string | null
  communication_notes?: string | null
  trade_ids?: number[]
}

/** Shape of the body for PATCH /api/v1/vendors/{id}. All fields optional. */
export type VendorUpdate = Partial<VendorCreate>

/** Shape of the body for PATCH /api/v1/work-orders/{id}. */
export type WorkOrderUpdate = {
  assigned_vendor_id?: number | null
}
