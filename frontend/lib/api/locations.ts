/**
 * Typed location endpoints (server-side).
 *
 * Locations are SC-sourced — there is no create/delete. We read them,
 * PATCH the Brenk enrichment fields, and manage gate codes via the
 * sub-resource endpoints.
 */

import { apiFetch } from './server'
import type {
  GateCode,
  GateCodeCreate,
  LocationDetail,
  LocationListParams,
  LocationListResponse,
  LocationUpdate,
  WorkOrderListResponse,
} from './types'

export function listLocations(
  params: LocationListParams = {},
): Promise<LocationListResponse> {
  return apiFetch<LocationListResponse>('/api/v1/locations/', { params })
}

export function getLocation(id: number): Promise<LocationDetail> {
  return apiFetch<LocationDetail>(`/api/v1/locations/${id}`)
}

export function listLocationWorkOrders(
  id: number,
  params: { page?: number; page_size?: number } = {},
): Promise<WorkOrderListResponse> {
  return apiFetch<WorkOrderListResponse>(
    `/api/v1/locations/${id}/work-orders`,
    { params },
  )
}

export function updateLocation(
  id: number,
  body: LocationUpdate,
): Promise<LocationDetail> {
  return apiFetch<LocationDetail>(`/api/v1/locations/${id}`, {
    method: 'PATCH',
    body,
  })
}

export function addGateCode(
  locationId: number,
  body: GateCodeCreate,
): Promise<GateCode> {
  return apiFetch<GateCode>(`/api/v1/locations/${locationId}/gate-codes`, {
    method: 'POST',
    body,
  })
}

export function invalidateGateCode(
  locationId: number,
  codeId: number,
): Promise<GateCode> {
  return apiFetch<GateCode>(
    `/api/v1/locations/${locationId}/gate-codes/${codeId}/invalidate`,
    { method: 'POST' },
  )
}
