/**
 * Typed work-order endpoints (server-side).
 *
 * Thin wrappers over apiFetch that pin the URL and the response type
 * for each route. Keeps page components from having to know the path
 * structure of the backend API.
 */

import { apiFetch } from './server'
import type {
  InvoiceSubmitPreview,
  VendorMessage,
  VendorSuggestionResponse,
  WorkOrderAttachment,
  WorkOrderDetail,
  WorkOrderListParams,
  WorkOrderListResponse,
  WorkOrderNoteRef,
  WorkOrderSyncStatus,
  WorkOrderSyncSummary,
  WorkOrderUpdate,
} from './types'

export function listWorkOrders(
  params: WorkOrderListParams = {},
): Promise<WorkOrderListResponse> {
  return apiFetch<WorkOrderListResponse>('/api/v1/work-orders/', { params })
}

export function getWorkOrder(id: number): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/work-orders/${id}`)
}

export function listWorkOrderNotes(id: number): Promise<WorkOrderNoteRef[]> {
  return apiFetch<WorkOrderNoteRef[]>(`/api/v1/work-orders/${id}/notes`)
}

export function listWorkOrderAttachments(
  id: number,
): Promise<WorkOrderAttachment[]> {
  return apiFetch<WorkOrderAttachment[]>(
    `/api/v1/work-orders/${id}/attachments`,
  )
}

export function getVendorMessage(id: number): Promise<VendorMessage> {
  return apiFetch<VendorMessage>(`/api/v1/work-orders/${id}/vendor-message`)
}

export function getVendorSuggestions(
  id: number,
): Promise<VendorSuggestionResponse> {
  return apiFetch<VendorSuggestionResponse>(
    `/api/v1/work-orders/${id}/suggest-vendors`,
  )
}

/** Add a sub-vendor to a work order (idempotent per vendor). */
export function addAssignment(
  workOrderId: number,
  body: { vendor_id: number; job_type_id?: number | null },
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(
    `/api/v1/work-orders/${workOrderId}/assignments`,
    { method: 'POST', body },
  )
}

/** Remove a sub-vendor from a work order. */
export function removeAssignment(
  workOrderId: number,
  vendorId: number,
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(
    `/api/v1/work-orders/${workOrderId}/assignments/${vendorId}`,
    { method: 'DELETE' },
  )
}

/** Update one vendor's assignment — per-vendor notify, paid, and/or aspect. */
export function updateAssignment(
  workOrderId: number,
  vendorId: number,
  body: {
    notified?: 'now' | 'clear'
    paid?: 'now' | 'clear'
    set_job_type?: boolean
    job_type_id?: number | null
  },
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(
    `/api/v1/work-orders/${workOrderId}/assignments/${vendorId}`,
    { method: 'PATCH', body },
  )
}

/** Save the itemized pricing — per-vendor payouts + WO markup/total — in one
 *  atomic call. `set_markup`/`set_total` distinguish "leave alone" from null. */
export function updatePricing(
  workOrderId: number,
  body: {
    costs: { vendor_id: number; labor_cost: string | null; material_cost: string | null }[]
    brenk_markup_percent?: string | null
    brenk_total_override?: string | null
    set_markup?: boolean
    set_total?: boolean
  },
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/work-orders/${workOrderId}/pricing`, {
    method: 'PUT',
    body,
  })
}

export function listCategories(): Promise<{ categories: string[] }> {
  return apiFetch<{ categories: string[] }>('/api/v1/categories/')
}

export type VendorEmailResult = {
  sent: boolean
  to_email: string
  photos_attached: number
  photos_total: number
}

export function sendVendorEmail(id: number): Promise<VendorEmailResult> {
  return apiFetch<VendorEmailResult>(
    `/api/v1/work-orders/${id}/send-vendor-email`,
    { method: 'POST' },
  )
}

export type VendorSmsResult = {
  sent: boolean
  to_phone: string
  photos_attached: number
  photos_total: number
}

export function sendVendorSms(id: number): Promise<VendorSmsResult> {
  return apiFetch<VendorSmsResult>(
    `/api/v1/work-orders/${id}/send-vendor-sms`,
    { method: 'POST' },
  )
}

export function getWorkOrderSyncStatus(): Promise<WorkOrderSyncStatus> {
  return apiFetch<WorkOrderSyncStatus>('/api/v1/work-orders/sync-status')
}

export function syncWorkOrdersFromSc(): Promise<WorkOrderSyncSummary> {
  return apiFetch<WorkOrderSyncSummary>('/api/v1/work-orders/sync', {
    method: 'POST',
  })
}

export function updateWorkOrder(
  id: number,
  body: WorkOrderUpdate,
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/work-orders/${id}`, {
    method: 'PATCH',
    body,
  })
}

export function getInvoicePreview(id: number): Promise<InvoiceSubmitPreview> {
  return apiFetch<InvoiceSubmitPreview>(
    `/api/v1/work-orders/${id}/invoice-preview`,
  )
}

export function submitInvoice(
  id: number,
  body: { invoice_text?: string | null },
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/work-orders/${id}/submit-invoice`, {
    method: 'POST',
    body,
  })
}
