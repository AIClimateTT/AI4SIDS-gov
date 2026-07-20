import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { OverviewSummary } from '@/types/dmcu'

export async function getOverview(): Promise<OverviewSummary> {
  return withApiError(async () => {
    const { data } = await apiClient.get<OverviewSummary>('/overview')
    return data
  })
}
