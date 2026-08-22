import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  AttachEventBody,
  CaptureCsvImportResult,
  CaptureCsvKind,
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

export async function previewCaptureSession(id: number): Promise<CaptureSession> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureSession>(
      `/capture/sessions/${id}/preview`,
    )
    return data
  })
}

export async function issueCaptureSession(id: number): Promise<CaptureFileResult> {
  return withApiError(async () => {
    const { data } = await apiClient.post<CaptureFileResult>(
      `/capture/sessions/${id}/issue`,
    )
    return data
  })
}

export async function importCaptureCsv(
  id: number,
  kind: CaptureCsvKind,
  file: File,
): Promise<CaptureCsvImportResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('kind', kind)
    form.append('file', file)
    const { data } = await apiClient.post<CaptureCsvImportResult>(
      `/capture/sessions/${id}/csv`,
      form,
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
