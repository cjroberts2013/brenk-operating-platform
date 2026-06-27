'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import {
  createJobType,
  deactivateJobType,
  updateJobType,
} from '@/lib/api/job-types'

type Result = { error?: string }

// Job types feed the category dropdown (work orders), the vendor-skill
// picker, and the categorizer — revalidate broadly after any change.
function revalidateConsumers() {
  revalidatePath('/settings')
  revalidatePath('/work-orders')
  revalidatePath('/work-orders/[id]', 'page')
  revalidatePath('/vendors')
}

export async function createJobTypeAction(
  name: string,
  description: string,
): Promise<Result> {
  try {
    await createJobType({ name: name.trim(), description: description.trim() || null })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidateConsumers()
  return {}
}

export async function updateJobTypeAction(
  id: number,
  body: { name?: string; description?: string | null },
): Promise<Result> {
  try {
    await updateJobType(id, body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidateConsumers()
  return {}
}

export async function setJobTypeActiveAction(
  id: number,
  active: boolean,
): Promise<Result> {
  try {
    if (active) await updateJobType(id, { is_active: true })
    else await deactivateJobType(id)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidateConsumers()
  return {}
}
