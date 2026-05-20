/**
 * Typed vendor endpoints (server-side).
 *
 * All variants of apiFetch return a JSON-parsed payload typed against
 * the backend Pydantic schemas. For DELETE we use `apiFetchVoid` since
 * the backend returns 204 with no body.
 */

import { apiFetch, apiFetchVoid } from './server'
import type {
  VendorCreate,
  VendorDetail,
  VendorListParams,
  VendorListResponse,
  VendorUpdate,
  WorkOrderDetail,
  WorkOrderUpdate,
} from './types'

export function listVendors(
  params: VendorListParams = {},
): Promise<VendorListResponse> {
  return apiFetch<VendorListResponse>('/api/v1/vendors/', { params })
}

export function getVendor(id: number): Promise<VendorDetail> {
  return apiFetch<VendorDetail>(`/api/v1/vendors/${id}`)
}

export function createVendor(body: VendorCreate): Promise<VendorDetail> {
  return apiFetch<VendorDetail>('/api/v1/vendors/', {
    method: 'POST',
    body,
  })
}

export function updateVendor(
  id: number,
  body: VendorUpdate,
): Promise<VendorDetail> {
  return apiFetch<VendorDetail>(`/api/v1/vendors/${id}`, {
    method: 'PATCH',
    body,
  })
}

export function deleteVendor(id: number): Promise<void> {
  return apiFetchVoid(`/api/v1/vendors/${id}`, { method: 'DELETE' })
}

export function patchWorkOrder(
  id: number,
  body: WorkOrderUpdate,
): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/work-orders/${id}`, {
    method: 'PATCH',
    body,
  })
}
