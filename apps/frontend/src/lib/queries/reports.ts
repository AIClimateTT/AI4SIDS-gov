import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { createReport, getReport, getReports } from '@/lib/api/reports'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import { overviewKeys } from '@/lib/queries/overview'
import type {
  GenerateReportInput,
  ReportListParams,
} from '@/types/dmcu'

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
      toast.success('Report generated')
      onSuccess?.(created.id)
    },
    onError: (error: Error) =>
      toast.error('Failed to generate report', {
        description: error.message,
      }),
  })
}
