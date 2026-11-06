import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { SituationLogListParams, SituationLogListResponse } from '@/types/dmcu'

export async function getSituationLogs(
  params: SituationLogListParams = {},
): Promise<SituationLogListResponse> {
  return withApiError(async () => {
    const { data } = await apiClient.get<SituationLogListResponse>('/situation-logs', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 10,
        q: params.q,
        corporation: params.corporation,
        submission_id: params.submissionId,
      },
    })
    return data
  })
}
