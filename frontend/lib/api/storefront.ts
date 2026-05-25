/**
 * Storefront API client.
 *
 * `getStorefront` is the only function called by the public
 * marketing site — it uses the no-auth fetcher.
 *
 * The PATCH and PUT helpers are for the dashboard editor and run
 * server-side via the authenticated `apiFetch`.
 */

import { apiFetch } from './server'
import { publicFetch } from './public'
import type {
  Storefront,
  StorefrontServiceItem,
  StorefrontUpdate,
} from './types'

/** Public read — used by the marketing storefront. */
export function getStorefrontPublic(): Promise<Storefront> {
  return publicFetch<Storefront>('/api/v1/storefront/')
}

/** Authenticated read — used by the dashboard editor for the
 *  initial form values. Hits the same endpoint but through the
 *  authenticated client so the Network tab in dev shows a
 *  consistent flow. */
export function getStorefrontAdmin(): Promise<Storefront> {
  return apiFetch<Storefront>('/api/v1/storefront/')
}

export function updateStorefront(body: StorefrontUpdate): Promise<Storefront> {
  return apiFetch<Storefront>('/api/v1/storefront/', {
    method: 'PATCH',
    body,
  })
}

export function replaceServices(
  services: StorefrontServiceItem[],
): Promise<Storefront> {
  return apiFetch<Storefront>('/api/v1/storefront/services', {
    method: 'PUT',
    body: { services },
  })
}
