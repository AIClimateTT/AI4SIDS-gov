import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { ingestModule } from '@/lib/api/ingest'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import { overviewKeys } from '@/lib/queries/overview'
import type { IngestModuleName } from '@/types/dmcu'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const ingestKeys = {
  all: () => ['ingest'] as const,
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const ingestMutations = {
  upload: () =>
    mutationOptions({
      mutationFn: ({
        moduleName,
        file,
        corporation,
      }: {
        moduleName: IngestModuleName
        file: File
        corporation?: string
      }) => ingestModule(moduleName, file, corporation),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useIngestModule(onSuccess?: () => void) {
  const queryClient = useQueryClient()

  return useMutation({
    ...ingestMutations.upload(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      toast.success(
        `Ingested ${result.rows_inserted} inserted, ${result.rows_updated} updated`,
      )
      onSuccess?.()
    },
    onError: (error: Error) =>
      toast.error('Failed to ingest file', {
        description: error.message,
      }),
  })
}
