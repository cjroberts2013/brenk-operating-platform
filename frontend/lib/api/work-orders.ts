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
