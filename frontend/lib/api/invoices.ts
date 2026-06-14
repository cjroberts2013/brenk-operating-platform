/**
 * Typed invoice endpoints (server-side). Lists actual SC invoice records
 * synced from invoice webhooks. Distinct from the WO billing worklist.
 */

import { apiFetch } from './server'
import type { InvoiceListResponse } from './types'

export function listInvoices(
  params: {
    status?: string
    /** Named bucket: 'awaiting' | 'paid' | 'rejected'. Omit for all. */
    status_group?: string
    /** Free-text across invoice #, WO #, location, trade. */
    q?: string
    page?: number
    page_size?: number
  } = {},
): Promise<InvoiceListResponse> {
  return apiFetch<InvoiceListResponse>('/api/v1/invoices/', { params })
}
