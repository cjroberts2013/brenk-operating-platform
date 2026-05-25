'use server'

import { revalidatePath, revalidateTag } from 'next/cache'

import { ApiError } from '@/lib/api/server'
import {
  replaceServices,
  updateStorefront,
} from '@/lib/api/storefront'
import type {
  StorefrontServiceItem,
  StorefrontUpdate,
} from '@/lib/api/types'

export type EditorActionResult = { error: string | null }

/** Save page-level content fields. Pass null to clear a field. */
export async function saveStorefrontAction(
  patch: StorefrontUpdate,
): Promise<EditorActionResult> {
  try {
    await updateStorefront(patch)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  // Bust the editor page cache + the public-storefront tag so the
  // marketing site picks up the change on its next request.
  revalidatePath('/storefront')
  revalidateTag('storefront', 'max')
  return { error: null }
}

/** Replace the entire services list in one shot. */
export async function saveServicesAction(
  services: StorefrontServiceItem[],
): Promise<EditorActionResult> {
  try {
    await replaceServices(services)
  } catch (err) {
    if (err instanceof ApiError) return { error: err.detail }
    throw err
  }
  revalidatePath('/storefront')
  revalidateTag('storefront', 'max')
  return { error: null }
}
