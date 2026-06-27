'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import { createJobType } from '@/lib/api/job-types'
import * as vendorsApi from '@/lib/api/vendors'
import type { VendorSyncSummary } from '@/lib/api/vendors'
import type {
  JobType,
  VendorContactPreference,
  VendorCreate,
} from '@/lib/api/types'

export type VendorActionState = {
  error: string | null
  /** Bumped each time the action runs. Lets the UI detect "we submitted"
   * without conflating with the unsubmitted initial state. */
  attempt: number
}

// IMPORTANT: a "use server" file can only export *async functions* —
// no constants, no objects. The initial state for useActionState lives
// in the consuming Client Component, not here.

const CONTACT_PREFERENCES: VendorContactPreference[] = [
  'sms',
  'call',
  'email',
  'other',
]

function buildPayloadFromForm(formData: FormData): VendorCreate {
  const name = String(formData.get('name') ?? '').trim()
  if (!name) {
    throw new Error('name is required')
  }

  const get = (key: string): string | null => {
    const raw = formData.get(key)
    if (raw === null) return null
    const str = String(raw).trim()
    return str.length ? str : null
  }

  const contactPreferenceRaw = get('contact_preference')
  const contact_preference = CONTACT_PREFERENCES.includes(
    contactPreferenceRaw as VendorContactPreference,
  )
    ? (contactPreferenceRaw as VendorContactPreference)
    : null

  const mobileAppRaw = get('mobile_app_capable')
  const mobile_app_capable: boolean | null =
    mobileAppRaw === 'yes' ? true : mobileAppRaw === 'no' ? false : null

  // Job-type (skill) ids arrive as repeated values: getAll returns string[].
  const job_type_ids = formData
    .getAll('job_type_ids')
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n) && n > 0)

  return {
    name,
    phone: get('phone'),
    email: get('email'),
    notes: get('notes'),
    is_active: formData.get('is_active') === 'on',
    contact_preference,
    payment_terms: get('payment_terms'),
    service_area: get('service_area'),
    mobile_app_capable,
    markup_notes: get('markup_notes'),
    communication_notes: get('communication_notes'),
    job_type_ids,
  }
}

export async function createVendorAction(
  prev: VendorActionState,
  formData: FormData,
): Promise<VendorActionState> {
  const attempt = prev.attempt + 1

  let body: VendorCreate
  try {
    body = buildPayloadFromForm(formData)
  } catch (err) {
    return { error: (err as Error).message, attempt }
  }

  try {
    await vendorsApi.createVendor(body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  revalidatePath('/vendors')
  return { error: null, attempt }
}

export async function updateVendorAction(
  prev: VendorActionState,
  formData: FormData,
): Promise<VendorActionState> {
  const attempt = prev.attempt + 1
  const idRaw = formData.get('id')
  const id = Number(idRaw)
  if (!Number.isFinite(id) || id < 1) {
    return { error: 'invalid vendor id', attempt }
  }

  let body: VendorCreate
  try {
    body = buildPayloadFromForm(formData)
  } catch (err) {
    return { error: (err as Error).message, attempt }
  }

  try {
    await vendorsApi.updateVendor(id, body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  revalidatePath('/vendors')
  return { error: null, attempt }
}

/** Inline-create a job type from the vendor modal (e.g. a new trade arises
 *  while tagging a vendor). The new type joins the shared taxonomy. */
export async function createSkillAction(
  name: string,
): Promise<{ skill?: JobType; error?: string }> {
  const trimmed = name.trim()
  if (!trimmed) {
    return { error: 'name is required' }
  }
  try {
    const skill = await createJobType({ name: trimmed })
    return { skill }
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
}


export async function syncVendorsAction(): Promise<{
  summary?: VendorSyncSummary
  error?: string
}> {
  try {
    const summary = await vendorsApi.syncVendorsFromSc()
    revalidatePath('/vendors')
    return { summary }
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
}


export async function deleteVendorAction(formData: FormData): Promise<void> {
  const id = Number(formData.get('id'))
  if (!Number.isFinite(id) || id < 1) return
  try {
    await vendorsApi.deleteVendor(id)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      // Already gone — treat as success.
    } else {
      throw err
    }
  }
  revalidatePath('/vendors')
}
