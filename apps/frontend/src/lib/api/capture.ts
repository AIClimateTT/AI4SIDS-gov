import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  AttachEventBody,
  CaptureFileResult,
  CaptureSession,
  CaptureSessionUpdate,
} from '@/types/dmcu'

export async function listCaptureSessions(
  corporation: string,
  eventId?: number,
): Promise<CaptureSession[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<CaptureSession[]>('/capture/sessions', {
      params: eventId === undefined ? { corporation } : { corporation, event_id: eventId },
    })
    return data
  })
}

export async function createCaptureSession(
  corporation: string,
  eventId?: number,
): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureSession>('/capture/sessions', {
      corporation,
      ...(eventId === undefined ? {} : { event_id: eventId }),
    })
    return data
  })
}

export async function getCaptureSession(id: number): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.get<CaptureSession>(`/capture/sessions/${id}`)
    return data
  })
}

export async function postCaptureTurn(
  id: number,
  message: string,
): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureSession>(
      `/capture/sessions/${id}/turns`,
      { message },
    )
    return data
  })
}

export async function updateCaptureSession(
  id: number,
  payload: CaptureSessionUpdate,
): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.put<CaptureSession>(
      `/capture/sessions/${id}`,
      payload,
    )
    return data
  })
}

export async function fileCaptureSession(id: number): Promise<CaptureFileResult> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureFileResult>(
      `/capture/sessions/${id}/file`,
    )
    return data
  })
}

export async function attachCaptureEvent(
  id: number,
  body: AttachEventBody,
): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureSession>(
      `/capture/sessions/${id}/event`,
      body,
    )
    return data
  })
}
