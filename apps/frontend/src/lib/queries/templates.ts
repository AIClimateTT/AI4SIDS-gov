import {
  queryOptions,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  createTemplateVersion,
  getTemplateVersion,
  getTemplateVersions,
  getTemplates,
} from '@/lib/api/templates'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import type { CreateTemplateVersionInput } from '@/types/dmcu'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const templateKeys = {
  all: () => ['templates'] as const,
  lists: () => [...templateKeys.all(), 'list'] as const,
  list: () => [...templateKeys.lists()] as const,
  versions: (name: string) =>
    [...templateKeys.all(), 'versions', name] as const,
  detail: (name: string, version: number) =>
    [...templateKeys.all(), 'detail', name, version] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const templateQueries = {
  list: () =>
    queryOptions({
      queryKey: templateKeys.list(),
      queryFn: getTemplates,
    }),
  versions: (name: string) =>
    queryOptions({
      queryKey: templateKeys.versions(name),
      queryFn: () => getTemplateVersions(name),
      enabled: !!name,
    }),
  detail: (name: string, version: number) =>
    queryOptions({
      queryKey: templateKeys.detail(name, version),
      queryFn: () => getTemplateVersion(name, version),
      enabled: !!name && version > 0,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const templateMutations = {
  createVersion: () =>
    mutationOptions({
      mutationFn: (payload: CreateTemplateVersionInput) =>
        createTemplateVersion(payload),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useCreateTemplateVersion(
  onSuccess?: (created: { name: string; version: number }) => void,
) {
  const queryClient = useQueryClient()

  return useMutation({
    ...templateMutations.createVersion(),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: templateKeys.lists() })
      void queryClient.invalidateQueries({
        queryKey: templateKeys.versions(created.name),
      })
      toast.success(`Template v${created.version} created`)
      onSuccess?.(created)
    },
    onError: (error: Error) =>
      toast.error('Failed to create template version', {
        description: error.message,
      }),
  })
}
