'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { updateWorkOrder } from '@/lib/api/work-orders'
import type { WorkOrderUpdate } from '@/lib/api/types'

export type MarkupActionResult = { error: string | null }

export type SaveInvoiceInput = {
  /** Empty string clears, undefined leaves alone. */
  labor_cost?: string
  /** Empty string clears, undefined leaves alone. */
  material_cost?: string
  /** Empty string clears, undefined leaves alone. */
  markup_percent?: string
}

/** Save the markup helper's inputs (labor cost + material cost +
 *  markup %) in one PATCH. An empty string for any field clears
 *  that column. Undefined leaves it alone — lets callers update
 *  one field without touching the others.
 *
 *  All three fields are Brenk-confidential: never sent to
 *  ServiceChannel. SC only ever sees the final invoice total
 *  Daryl manually enters into SC's own invoice form. */
export async function saveInvoiceAction(
  workOrderId: number,
  input: SaveInvoiceInput,
): Promise<MarkupActionResult> {
  const body: WorkOrderUpdate = {}

  const numericField = (
    raw: string | undefined,
    label: string,
    max?: number,
  ): { ok: true; value: string | null } | { ok: false; error: string } => {
    if (raw === undefined) return { ok: true, value: null }
    const trimmed = raw.trim()
    if (trimmed.length === 0) return { ok: true, value: null }
    const n = Number(trimmed)
    if (!Number.isFinite(n) || n < 0) {
      return { ok: false, error: `${label} must be a non-negative number.` }
    }
    if (max !== undefined && n > max) {
      return {
        ok: false,
        error: `${label} must be ${max} or less.`,
      }
    }
    return { ok: true, value: trimmed }
  }

  if (input.labor_cost !== undefined) {
    const r = numericField(input.labor_cost, 'Labor cost')
    if (!r.ok) return { error: r.error }
    body.brenk_labor_cost = r.value
  }
  if (input.material_cost !== undefined) {
    const r = numericField(input.material_cost, 'Material cost')
    if (!r.ok) return { error: r.error }
    body.brenk_material_cost = r.value
  }
  if (input.markup_percent !== undefined) {
    const r = numericField(input.markup_percent, 'Markup', 1000)
    if (!r.ok) return { error: r.error }
    body.brenk_markup_percent = r.value
  }

  if (Object.keys(body).length === 0) {
    // Nothing to do — caller passed an empty object. Not an error.
    return { error: null }
  }

  try {
    await updateWorkOrder(workOrderId, body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath(`/work-orders/${workOrderId}`)
  revalidatePath('/invoices')
  revalidatePath('/')
  return { error: null }
}

/** Toggle the paid state. `mark` true → stamp now(), false → clear. */
export async function setPaidAction(
  workOrderId: number,
  mark: boolean,
): Promise<MarkupActionResult> {
  try {
    await updateWorkOrder(workOrderId, { paid: mark ? 'now' : 'clear' })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath(`/work-orders/${workOrderId}`)
  revalidatePath('/invoices')
  revalidatePath('/')
  return { error: null }
}
