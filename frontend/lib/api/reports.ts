import { apiFetch } from '@/lib/api/server'

import type { PayablesResponse, ReportsSummary } from './types'

/** Markup / spend analytics across all marked-up work orders. */
export function getReportsSummary(): Promise<ReportsSummary> {
  return apiFetch<ReportsSummary>('/api/v1/reports/summary')
}

/** Outstanding sub-vendor payouts — what Brenk still owes. */
export function getPayables(): Promise<PayablesResponse> {
  return apiFetch<PayablesResponse>('/api/v1/reports/payables')
}
