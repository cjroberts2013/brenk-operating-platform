import { apiFetch } from './server'
import type { JobType } from './types'

/** All job types (active + retired), in display order. */
export function listJobTypes(): Promise<JobType[]> {
  return apiFetch<JobType[]>('/api/v1/job-types/')
}

export function createJobType(body: {
  name: string
  description?: string | null
}): Promise<JobType> {
  return apiFetch<JobType>('/api/v1/job-types/', { method: 'POST', body })
}

export function updateJobType(
  id: number,
  body: { name?: string; description?: string | null; is_active?: boolean },
): Promise<JobType> {
  return apiFetch<JobType>(`/api/v1/job-types/${id}`, { method: 'PATCH', body })
}

/** Soft-retire a job type (hidden from pickers + categorizer; history kept). */
export function deactivateJobType(id: number): Promise<JobType> {
  return apiFetch<JobType>(`/api/v1/job-types/${id}`, { method: 'DELETE' })
}
