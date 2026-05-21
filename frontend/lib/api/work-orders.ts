/**
 * Typed work-order endpoints (server-side).
 *
 * Thin wrappers over apiFetch that pin the URL and the response type
 * for each route. Keeps page components from having to know the path
 * structure of the backend API.
 */

import { apiFetch } from './server'
import type {
  WorkOrderDetail,
  WorkOrderListParams,
  WorkOrderListResponse,
  WorkOrderNoteRef,
  WorkOrderSyncStatus,
  WorkOrderSyncSummary,
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
