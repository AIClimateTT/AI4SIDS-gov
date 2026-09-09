import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { createReport, getReport, getReports, postReportRating } from '@/lib/api/reports'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import { overviewKeys } from '@/lib/queries/overview'
import { qualityKeys } from '@/lib/queries/quality'
import type {
  GenerateReportInput,
  RatingInput,
  ReportListParams,
  ReportStatus,
} from '@/types/dmcu'

export function isReportJobPending(status?: ReportStatus) {
  return status === 'queued' || status === 'running'
}

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const reportKeys = {
  all: () => ['reports'] as const,
  lists: () => [...reportKeys.all(), 'list'] as const,
  list: (params: ReportListParams = {}) =>
    [...reportKeys.lists(), params] as const,
  details: () => [...reportKeys.all(), 'detail'] as const,
  detail: (id: string) => [...reportKeys.details(), id] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const reportQueries = {
  list: (params: ReportListParams = {}) =>
    queryOptions({
      queryKey: reportKeys.list(params),
      queryFn: () => getReports(params),
    }),
  detail: (id: string) =>
    queryOptions({
      queryKey: reportKeys.detail(id),
      queryFn: () => getReport(id),
      enabled: !!id,
      refetchInterval: (query) =>
        isReportJobPending(query.state.data?.status) ? 2000 : false,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const reportMutations = {
  create: () =>
    mutationOptions({
      mutationFn: (payload: GenerateReportInput) => createReport(payload),
    }),
  rate: () =>
    mutationOptions({
      mutationFn: ({
        reportId,
        rating,
        comment,
      }: RatingInput & { reportId: string }) =>
        postReportRating(reportId, { rating, comment }),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useCreateReport(onSuccess?: (id: string) => void) {
  const queryClient = useQueryClient()

  return useMutation({
    ...reportMutations.create(),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      toast.success(
        isReportJobPending(created.status) ? 'Report started' : 'Report generated',
      )
      onSuccess?.(created.id)
    },
    onError: (error: Error) =>
      toast.error('Failed to generate report', {
        description: error.message,
      }),
  })
}

export function useRateReport(reportId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    ...reportMutations.rate(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) })
      void queryClient.invalidateQueries({ queryKey: qualityKeys.summary() })
      toast.success('Rating saved')
    },
    onError: (error: Error) =>
      toast.error('Failed to save rating', {
        description: error.message,
      }),
  })
}
