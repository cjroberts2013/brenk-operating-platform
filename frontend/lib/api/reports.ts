import { apiFetch } from '@/lib/api/server'

import type { ReportsSummary } from './types'

/** Markup / spend analytics across all marked-up work orders. */
export function getReportsSummary(): Promise<ReportsSummary> {
  return apiFetch<ReportsSummary>('/api/v1/reports/summary')
}
