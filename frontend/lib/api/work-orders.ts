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
