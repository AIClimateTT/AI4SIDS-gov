import type { CaptureSession } from '@/types/dmcu'

export type SitrepHref =
  | { to: '/corp/c/$sessionId'; params: { sessionId: string } }
  | { to: '/corp/events/$eventId'; params: { eventId: string } }
  | { to: '/corp' }

export function resolveSitrepHref(
  submission: { id: number; event_id: number | null },
  sessions: CaptureSession[],
): SitrepHref {
  const filed = sessions.find((session) => session.submission_id === submission.id)
  if (filed) {
    return { to: '/corp/c/$sessionId', params: { sessionId: String(filed.id) } }
  }

  if (submission.event_id != null) {
    const onEvent = sessions.find((session) => session.event_id === submission.event_id)
    if (onEvent) {
      return {
        to: '/corp/c/$sessionId',
        params: { sessionId: String(onEvent.id) },
      }
    }
    return {
      to: '/corp/events/$eventId',
      params: { eventId: String(submission.event_id) },
    }
  }

  return { to: '/corp' }
}
