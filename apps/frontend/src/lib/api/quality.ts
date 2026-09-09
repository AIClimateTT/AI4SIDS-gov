import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { QualityEval, QualitySummary } from '@/types/dmcu'

export async function getQualitySummary(): Promise<QualitySummary> {
  return withApiError(async () => {
    const { data } = await apiClient.get<QualitySummary>('/quality/summary')
    return data
  })
}

export async function patchClaimVerdict(
  reportId: string,
  claimId: string,
  verdict: 'supported' | 'unsupported',
): Promise<QualityEval> {
  return withApiError(async () => {
    const { data } = await apiClient.patch<QualityEval>(
      `/reports/${reportId}/claims/${claimId}`,
      { verdict },
    )
    return data
  })
}
