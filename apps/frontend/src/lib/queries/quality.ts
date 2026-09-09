import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { getQualitySummary, patchClaimVerdict } from '@/lib/api/quality'
import { reportKeys } from '@/lib/queries/reports'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const qualityKeys = {
  all: () => ['quality'] as const,
  summary: () => [...qualityKeys.all(), 'summary'] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const qualityQueries = {
  summary: () =>
    queryOptions({
      queryKey: qualityKeys.summary(),
      queryFn: getQualitySummary,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const qualityMutations = {
  verdict: () =>
    mutationOptions({
      mutationFn: ({
        reportId,
        claimId,
        verdict,
      }: {
        reportId: string
        claimId: string
        verdict: 'supported' | 'unsupported'
      }) => patchClaimVerdict(reportId, claimId, verdict),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useQualitySummary() {
  return useQuery(qualityQueries.summary())
}

export function useVerdictClaim(reportId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    ...qualityMutations.verdict(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) })
      void queryClient.invalidateQueries({ queryKey: qualityKeys.summary() })
      toast.success('Claim verdict saved')
    },
    onError: (error: Error) =>
      toast.error('Failed to save verdict', {
        description: error.message,
      }),
  })
}
