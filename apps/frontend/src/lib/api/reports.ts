import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  GenerateReportInput,
  GenerateReportResult,
  ReportDetail,
  ReportListParams,
  ReportListResponse,
} from '@/types/dmcu'

export async function getReports(
  params: ReportListParams = {},
): Promise<ReportListResponse> {
  return withApiError(async () => {
    const { data } = await apiClient.get<ReportListResponse>('/reports', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 10,
        q: params.q,
        status: params.status === 'all' ? undefined : params.status,
        sort_by: params.sortBy ?? 'created_at',
        sort_order: params.sortOrder ?? 'desc',
      },
    })
    return data
  })
}

export async function getReport(id: string): Promise<ReportDetail> {
  return withApiError(async () => {
    const { data } = await apiClient.get<ReportDetail>(`/reports/${id}`)
    return data
  })
}

export async function createReport(
  payload: GenerateReportInput,
): Promise<GenerateReportResult> {
  return withApiError(async () => {
    const { data } = await apiClient.post<GenerateReportResult>(
      '/reports',
      payload,
    )
    return data
  })
}
