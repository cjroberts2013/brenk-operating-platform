import { apiFetch } from '@/lib/api/server'

import type { DashboardPipeline } from './types'

export function getDashboardPipeline(): Promise<DashboardPipeline> {
  return apiFetch<DashboardPipeline>('/api/v1/dashboard/pipeline')
}
