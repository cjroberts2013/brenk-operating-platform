'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { patchWorkOrder } from '@/lib/api/vendors'
import { syncWorkOrdersFromSc } from '@/lib/api/work-orders'
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
