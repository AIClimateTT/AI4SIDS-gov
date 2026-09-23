import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { IncidentListParams, IncidentListResponse } from '@/types/dmcu'

export async function getIncidents(
  params: IncidentListParams = {},
): Promise<IncidentListResponse> {
  return withApiError(async () => {
    const { data } = await apiClient.get<IncidentListResponse>('/incidents', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 10,
        q: params.q,
        source: params.source === 'all' ? undefined : params.source,
      },
    })
    return data
  })
}
