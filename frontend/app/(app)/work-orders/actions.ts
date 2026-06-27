'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { patchWorkOrder } from '@/lib/api/vendors'
import {
  sendVendorEmail,
  syncWorkOrdersFromSc,
  type VendorEmailResult,
} from '@/lib/api/work-orders'
import type { WorkOrderSyncSummary } from '@/lib/api/types'

export type AssignVendorState = {
  error: string | null
  attempt: number
}

export async function assignVendorAction(
  prev: AssignVendorState,
  formData: FormData,
): Promise<AssignVendorState> {
  const attempt = prev.attempt + 1

  const workOrderId = Number(formData.get('work_order_id'))
  if (!Number.isFinite(workOrderId) || workOrderId < 1) {
    return { error: 'invalid work order id', attempt }
  }

  const raw = formData.get('assigned_vendor_id')
  let assigned_vendor_id: number | null
  if (raw === null || raw === '') {
    assigned_vendor_id = null
  } else {
    const n = Number(raw)
    if (!Number.isFinite(n) || n < 1) {
      return { error: 'invalid vendor selection', attempt }
    }
    assigned_vendor_id = n
  }

  try {
    await patchWorkOrder(workOrderId, { assigned_vendor_id })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  // Both the WO detail page and any vendor's detail page may now show
  // different data — revalidate broadly.
  revalidatePath('/work-orders')
  revalidatePath('/vendors')
  return { error: null, attempt }
}


/** One-click assign for the suggestion panel. Imperative (vendor id passed
 *  directly) rather than the FormData/useActionState shape of
 *  `assignVendorAction`, since the suggested vendor is known up front. */
export async function quickAssignVendorAction(
  workOrderId: number,
  vendorId: number,
): Promise<{ error?: string }> {
  if (!Number.isFinite(workOrderId) || workOrderId < 1) {
    return { error: 'invalid work order id' }
  }
  if (!Number.isFinite(vendorId) || vendorId < 1) {
    return { error: 'invalid vendor selection' }
  }
  try {
    await patchWorkOrder(workOrderId, { assigned_vendor_id: vendorId })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/work-orders')
  revalidatePath('/vendors')
  return {}
}


export type CategoryState = {
  error: string | null
  attempt: number
}

/** Confirm the AI category (no value) or override it (a category value). */
export async function setCategoryAction(
  prev: CategoryState,
  formData: FormData,
): Promise<CategoryState> {
  const attempt = prev.attempt + 1
  const workOrderId = Number(formData.get('work_order_id'))
  if (!Number.isFinite(workOrderId) || workOrderId < 1) {
    return { error: 'invalid work order id', attempt }
  }

  const raw = formData.get('brenk_category')
  const body =
    raw === null
      ? { category_action: 'confirm' as const }
      : { brenk_category: String(raw) }

  try {
    await patchWorkOrder(workOrderId, body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  revalidatePath(`/work-orders/${workOrderId}`)
  revalidatePath('/reports')
  return { error: null, attempt }
}


export async function sendVendorEmailAction(
  workOrderId: number,
): Promise<{ result?: VendorEmailResult; error?: string }> {
  try {
    const result = await sendVendorEmail(workOrderId)
    // Refresh the detail page — the WO is now marked vendor-notified.
    revalidatePath(`/work-orders/${workOrderId}`)
    return { result }
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
}


export async function syncWorkOrdersAction(): Promise<{
  summary?: WorkOrderSyncSummary
  error?: string
}> {
  try {
    const summary = await syncWorkOrdersFromSc()
    // Revalidate both the list (rows + last-sync header line) and any
    // currently-open detail page.
    revalidatePath('/work-orders')
    revalidatePath('/work-orders/[id]', 'page')
    return { summary }
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
}
