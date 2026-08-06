import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  createEvent,
  fileSubmission,
  getEvents,
  getSubmission,
  getSubmissions,
} from '@/lib/api/submissions'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import type { CreateEventInput, FileSubmissionInput } from '@/types/dmcu'

type SubmissionListParams = Parameters<typeof getSubmissions>[0]

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const eventKeys = {
  all: () => ['events'] as const,
  lists: () => [...eventKeys.all(), 'list'] as const,
  list: (corporation: string) => [...eventKeys.lists(), corporation] as const,
}

export const submissionKeys = {
  all: () => ['submissions'] as const,
  lists: () => [...submissionKeys.all(), 'list'] as const,
  list: (params: SubmissionListParams = {}) =>
    [...submissionKeys.lists(), params] as const,
  details: () => [...submissionKeys.all(), 'detail'] as const,
  detail: (id: number) => [...submissionKeys.details(), id] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const eventQueries = {
  list: (corporation: string) =>
    queryOptions({
      queryKey: eventKeys.list(corporation),
      queryFn: () => getEvents(corporation),
      enabled: !!corporation,
    }),
}

export const submissionQueries = {
  list: (params: SubmissionListParams = {}) =>
    queryOptions({
      queryKey: submissionKeys.list(params),
      queryFn: () => getSubmissions(params),
    }),
  detail: (id: number) =>
    queryOptions({
      queryKey: submissionKeys.detail(id),
      queryFn: () => getSubmission(id),
      enabled: !!id,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const eventMutations = {
  create: () =>
    mutationOptions({
      mutationFn: (input: CreateEventInput) => createEvent(input),
    }),
}

export const submissionMutations = {
  file: () =>
    mutationOptions({
      mutationFn: (input: FileSubmissionInput) => fileSubmission(input),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useCreateEvent(onSuccess?: (id: number) => void) {
  const queryClient = useQueryClient()

  return useMutation({
    ...eventMutations.create(),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() })
      toast.success('Event created')
      onSuccess?.(created.id)
    },
    onError: (error: Error) =>
      toast.error('Failed to create event', {
        description: error.message,
      }),
  })
}

export function useFileSubmission(onSuccess?: (id: number) => void) {
  const queryClient = useQueryClient()

  return useMutation({
    ...submissionMutations.file(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
      toast.success('Submission filed')
      onSuccess?.(result.submission_id)
    },
    onError: (error: Error) =>
      toast.error('Failed to file submission', {
        description: error.message,
      }),
  })
}
