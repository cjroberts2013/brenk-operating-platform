'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { patchWorkOrder } from '@/lib/api/vendors'
import {
  addAssignment,
  removeAssignment,
  sendVendorEmail,
  sendVendorSms,
  syncWorkOrdersFromSc,
  updateAssignment,
  type VendorEmailResult,
  type VendorSmsResult,
} from '@/lib/api/work-orders'
import type { WorkOrderSyncSummary } from '@/lib/api/types'



/** Add a vendor to a WO's assignment set (multi-vendor). Used by the
 *  suggestion panel and the assignment control's "Add vendor". */
export async function addAssignmentAction(
  workOrderId: number,
  vendorId: number,
  jobTypeId?: number | null,
): Promise<{ error?: string }> {
  if (!Number.isFinite(vendorId) || vendorId < 1) {
    return { error: 'invalid vendor selection' }
  }
  try {
    await addAssignment(workOrderId, { vendor_id: vendorId, job_type_id: jobTypeId })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/work-orders')
  revalidatePath('/vendors')
  return {}
}

/** Remove a vendor from a WO's assignment set. */
export async function removeAssignmentAction(
  workOrderId: number,
  vendorId: number,
): Promise<{ error?: string }> {
  try {
    await removeAssignment(workOrderId, vendorId)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/work-orders')
  revalidatePath('/vendors')
  return {}
}

/** Mark one assigned vendor notified (or clear it). */
export async function setAssignmentNotifiedAction(
  workOrderId: number,
  vendorId: number,
  notified: boolean,
): Promise<{ error?: string }> {
  try {
    await updateAssignment(workOrderId, vendorId, {
      notified: notified ? 'now' : 'clear',
    })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/work-orders')
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


export async function sendVendorSmsAction(
  workOrderId: number,
): Promise<{ result?: VendorSmsResult; error?: string }> {
  try {
    const result = await sendVendorSms(workOrderId)
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
