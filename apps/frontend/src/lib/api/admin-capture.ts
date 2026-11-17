import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'

/** One capture session as the admin register sees it: that it exists, not what it says. */
export type AdminCaptureSession = {
  id: number
  corporation: string
  event_id: number | null
  status: 'draft' | 'filed' | string
  as_at: string
  message_count: number
  officer_message_count: number
  submission_id: number | null
  report_id: string | null
  has_sitrep: boolean
  created_at: string
  updated_at: string
}

export type TranscriptFormat = 'md' | 'json'

export async function getAdminCaptureSessions(
  corporation: string,
): Promise<AdminCaptureSession[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<AdminCaptureSession[]>('/admin/capture/sessions', {
      params: { corporation },
    })
    return data
  })
}

function filenameFrom(disposition: unknown, fallback: string): string {
  if (typeof disposition !== 'string') return fallback
  const match = /filename="?([^";]+)"?/.exec(disposition)
  return match?.[1] ?? fallback
}

/** Fetch with the bearer token, then hand the browser the file. */
export async function downloadCaptureTranscript(
  sessionId: number,
  format: TranscriptFormat,
): Promise<void> {
  return withApiError(async () => {
    const response = await apiClient.get<Blob>(
      `/admin/capture/sessions/${sessionId}/transcript`,
      { params: { format }, responseType: 'blob' },
    )
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filenameFrom(
      response.headers['content-disposition'],
      `capture-${sessionId}.${format}`,
    )
    link.click()
    URL.revokeObjectURL(url)
  })
}
