import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  attachCaptureEvent,
  createCaptureSession,
  fileCaptureSession,
  getCaptureSession,
  listCaptureSessions,
  postCaptureTurn,
  updateCaptureSession,
} from '@/lib/api/capture'
import { overviewKeys } from '@/lib/queries/overview'
import { eventKeys, submissionKeys } from '@/lib/queries/submissions'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import type { AttachEventBody, CaptureSessionUpdate } from '@/types/dmcu'

export const captureKeys = {
  all: () => ['capture'] as const,
  lists: () => [...captureKeys.all(), 'list'] as const,
  list: (corporation: string, eventId?: number) =>
    [...captureKeys.lists(), corporation, eventId] as const,
  details: () => [...captureKeys.all(), 'detail'] as const,
  detail: (id: number) => [...captureKeys.details(), id] as const,
}

export const captureQueries = {
  list: (corporation: string, eventId?: number) =>
    queryOptions({
      queryKey: captureKeys.list(corporation, eventId),
      queryFn: () => listCaptureSessions(corporation, eventId),
      enabled: !!corporation,
    }),
  detail: (id: number) =>
    queryOptions({
      queryKey: captureKeys.detail(id),
      queryFn: () => getCaptureSession(id),
      enabled: Number.isInteger(id) && id > 0,
    }),
}

export const captureMutations = {
  create: () =>
    mutationOptions({
      mutationFn: (input: { corporation: string; eventId: number }) =>
        createCaptureSession(input.corporation, input.eventId),
    }),
  turn: () =>
    mutationOptions({
      mutationFn: (input: { id: number; message: string }) =>
        postCaptureTurn(input.id, input.message),
    }),
  update: () =>
    mutationOptions({
      mutationFn: (input: { id: number; payload: CaptureSessionUpdate }) =>
        updateCaptureSession(input.id, input.payload),
    }),
  file: () =>
    mutationOptions({
      mutationFn: (id: number) => fileCaptureSession(id),
    }),
}

export function useCreateCaptureSession() {
  const queryClient = useQueryClient()
  return useMutation({
    ...captureMutations.create(),
    onSuccess: (session) => {
      queryClient.setQueryData(captureKeys.detail(session.id), session)
      void queryClient.invalidateQueries({ queryKey: captureKeys.lists() })
    },
    onError: (error: Error) =>
      toast.error('Failed to start conversation', {
        description: error.message,
      }),
  })
}

export function useCaptureTurn() {
  const queryClient = useQueryClient()
  return useMutation({
    ...captureMutations.turn(),
    onSuccess: (session) => {
      queryClient.setQueryData(captureKeys.detail(session.id), session)
    },
    onError: (error: Error) =>
      toast.error('Failed to send update', {
        description: error.message,
      }),
  })
}

export function useUpdateCaptureSession() {
  const queryClient = useQueryClient()
  return useMutation({
    ...captureMutations.update(),
    onSuccess: (session) => {
      queryClient.setQueryData(captureKeys.detail(session.id), session)
    },
    onError: (error: Error) =>
      toast.error('Failed to save capture', {
        description: error.message,
      }),
  })
}

export function useAttachCaptureEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: number; body: AttachEventBody }) =>
      attachCaptureEvent(input.id, input.body),
    onSuccess: (session) => {
      queryClient.setQueryData(captureKeys.detail(session.id), session)
      void queryClient.invalidateQueries({ queryKey: captureKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
    },
    onError: (error: Error) =>
      toast.error('Failed to attach event', { description: error.message }),
  })
}

export function useFileCaptureSession() {
  const queryClient = useQueryClient()
  return useMutation({
    ...captureMutations.file(),
    onSuccess: (result) => {
      queryClient.setQueryData(captureKeys.detail(result.session.id), result.session)
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: eventKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: overviewKeys.summary() })
      toast.success('Submission filed')
    },
    onError: (error: Error) =>
      toast.error('Failed to file submission', {
        description: error.message,
      }),
  })
}
