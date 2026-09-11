import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  adjustWhatsAppDraft,
  extractWhatsApp,
  generateWhatsAppBriefing,
  getWhatsAppDraft,
  listWhatsAppDrafts,
  promoteWhatsAppDraft,
  updateWhatsAppDraft,
} from '@/lib/api/whatsapp'
import { overviewKeys } from '@/lib/queries/overview'
import { reportKeys } from '@/lib/queries/reports'
import { eventKeys, submissionKeys } from '@/lib/queries/submissions'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import type { WhatsAppDraftUpdate } from '@/types/dmcu'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const whatsappKeys = {
  all: () => ['whatsapp'] as const,
  drafts: () => [...whatsappKeys.all(), 'draft'] as const,
  draft: (id: number) => [...whatsappKeys.drafts(), id] as const,
  lists: () => [...whatsappKeys.all(), 'list'] as const,
  list: () => [...whatsappKeys.lists()] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export function isWhatsAppExtractPending(status?: string) {
  return status === 'queued' || status === 'running'
}

export const whatsappQueries = {
  list: () =>
    queryOptions({
      queryKey: whatsappKeys.list(),
      queryFn: listWhatsAppDrafts,
    }),
  draft: (id: number) =>
    queryOptions({
      queryKey: whatsappKeys.draft(id),
      queryFn: () => getWhatsAppDraft(id),
      enabled: Number.isInteger(id) && id > 0,
      refetchInterval: (query) =>
        isWhatsAppExtractPending(query.state.data?.status) ? 2000 : false,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const whatsappMutations = {
  extract: () =>
    mutationOptions({
      mutationFn: (input: { file?: File; text?: string; asAt: string }) =>
        extractWhatsApp(input),
    }),
  update: () =>
    mutationOptions({
      mutationFn: ({
        id,
        payload,
      }: {
        id: number
        payload: WhatsAppDraftUpdate
      }) => updateWhatsAppDraft(id, payload),
    }),
  adjust: () =>
    mutationOptions({
      mutationFn: ({ id, instruction }: { id: number; instruction: string }) =>
        adjustWhatsAppDraft(id, instruction),
    }),
  briefing: () =>
    mutationOptions({
      mutationFn: (id: number) => generateWhatsAppBriefing(id),
    }),
  promote: () =>
    mutationOptions({
      mutationFn: (id: number) => promoteWhatsAppDraft(id),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useExtractWhatsApp() {
  const queryClient = useQueryClient()
  return useMutation({
    ...whatsappMutations.extract(),
    onSuccess: (draft) => {
      queryClient.setQueryData(whatsappKeys.draft(draft.id), draft)
      void queryClient.invalidateQueries({ queryKey: whatsappKeys.lists() })
    },
    onError: (error: Error) =>
      toast.error('Failed to extract chat', {
        description: error.message,
      }),
  })
}

export function useUpdateWhatsAppDraft() {
  const queryClient = useQueryClient()
  return useMutation({
    ...whatsappMutations.update(),
    onSuccess: (draft) => {
      queryClient.setQueryData(whatsappKeys.draft(draft.id), draft)
    },
    onError: (error: Error) =>
      toast.error('Failed to save draft', {
        description: error.message,
      }),
  })
}

export function useAdjustWhatsAppDraft() {
  const queryClient = useQueryClient()
  return useMutation({
    ...whatsappMutations.adjust(),
    onSuccess: (draft) => {
      queryClient.setQueryData(whatsappKeys.draft(draft.id), draft)
      toast.success('Extraction updated')
    },
    onError: (error: Error) =>
      toast.error('Failed to adjust extraction', {
        description: error.message,
      }),
  })
}

export function useGenerateWhatsAppBriefing() {
  const queryClient = useQueryClient()
  return useMutation({
    ...whatsappMutations.briefing(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      toast.success('Briefing started')
    },
    onError: (error: Error) =>
      toast.error('Failed to generate briefing', {
        description: error.message,
      }),
  })
}

export function usePromoteWhatsAppDraft() {
  const queryClient = useQueryClient()
  return useMutation({
    ...whatsappMutations.promote(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      toast.success(
        `Filed ${result.submissions.length} submission${
          result.submissions.length === 1 ? '' : 's'
        }`,
      )
    },
    onError: (error: Error) =>
      toast.error('Failed to file to store', {
        description: error.message,
      }),
  })
}
