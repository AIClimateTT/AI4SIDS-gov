import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { uploadFieldData } from '@/lib/api/ingest'
import { incidentKeys } from '@/lib/queries/incidents'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import { overviewKeys } from '@/lib/queries/overview'

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
      mutationFn: ({ file }: { file: File }) => uploadFieldData(file),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useUploadFieldData(onSuccess?: () => void) {
  const queryClient = useQueryClient()

  return useMutation({
    ...ingestMutations.upload(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      void queryClient.invalidateQueries({ queryKey: incidentKeys.lists() })
      toast.success(
        `${result.rows_inserted} new, ${result.rows_updated} updated`,
      )
      onSuccess?.()
    },
    onError: (error: Error) =>
      toast.error('Upload rejected', {
        description: error.message,
      }),
  })
}
