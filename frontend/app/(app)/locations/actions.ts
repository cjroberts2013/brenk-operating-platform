'use server'

import { revalidatePath } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import * as locationsApi from '@/lib/api/locations'
import type { LocationRating, LocationUpdate } from '@/lib/api/types'

// IMPORTANT: a "use server" file can only export *async functions* — the
// initial useActionState value lives in the consuming Client Component.

export type LocationActionState = {
  error: string | null
  /** Bumped each time the action runs, so the UI can detect a fresh
   *  success without conflating it with the initial mount. */
  attempt: number
}

const RATINGS: LocationRating[] = ['good', 'watch', 'problem']

function get(formData: FormData, key: string): string | null {
  const raw = formData.get(key)
  if (raw === null) return null
  const str = String(raw).trim()
  return str.length ? str : null
}

export async function updateLocationAction(
  prev: LocationActionState,
  formData: FormData,
): Promise<LocationActionState> {
  const attempt = prev.attempt + 1
  const id = Number(formData.get('id'))
  if (!Number.isFinite(id) || id < 1) {
    return { error: 'invalid location id', attempt }
  }

  const ratingRaw = get(formData, 'rating')
  const rating = RATINGS.includes(ratingRaw as LocationRating)
    ? (ratingRaw as LocationRating)
    : null

  const body: LocationUpdate = {
    district_manager_name: get(formData, 'district_manager_name'),
    district_manager_phone: get(formData, 'district_manager_phone'),
    district_manager_email: get(formData, 'district_manager_email'),
    rating,
    description: get(formData, 'description'),
  }

  try {
    await locationsApi.updateLocation(id, body)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  revalidatePath('/locations')
  revalidatePath(`/locations/${id}`)
  return { error: null, attempt }
}

export async function addGateCodeAction(
  prev: LocationActionState,
  formData: FormData,
): Promise<LocationActionState> {
  const attempt = prev.attempt + 1
  const id = Number(formData.get('location_id'))
  if (!Number.isFinite(id) || id < 1) {
    return { error: 'invalid location id', attempt }
  }
  const code = String(formData.get('code') ?? '').trim()
  if (!code) {
    return { error: 'A code is required.', attempt }
  }
  const label = String(formData.get('label') ?? '').trim()

  try {
    await locationsApi.addGateCode(id, { code, label: label || null })
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail, attempt }
    throw err
  }

  revalidatePath(`/locations/${id}`)
  return { error: null, attempt }
}

export async function invalidateGateCodeAction(formData: FormData): Promise<void> {
  const id = Number(formData.get('location_id'))
  const codeId = Number(formData.get('code_id'))
  if (!Number.isFinite(id) || !Number.isFinite(codeId)) return
  try {
    await locationsApi.invalidateGateCode(id, codeId)
  } catch (err) {
    // 404 (already gone / not under this location) → treat as done.
    if (err instanceof ApiError && err.status === 404) {
      // no-op
    } else {
      throw err
    }
  }
  revalidatePath(`/locations/${id}`)
}
