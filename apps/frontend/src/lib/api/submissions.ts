import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  CreateEventInput,
  EventSummary,
  FileSubmissionInput,
  SubmissionDetail,
  SubmissionIngestResult,
  SubmissionSummary,
} from '@/types/dmcu'

export async function getEvents(corporation: string): Promise<EventSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<EventSummary[]>('/events', {
      params: { corporation },
    })
    return data
  })
}

export async function createEvent(input: CreateEventInput): Promise<EventSummary> {
  return withApiError(async () => {
    const { data } = await apiClient.post<EventSummary>('/events', input)
    return data
  })
}

export async function getSubmissions(params: {
  corporation?: string
  event_id?: number
  date_from?: string
  date_to?: string
}): Promise<SubmissionSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<SubmissionSummary[]>('/submissions', { params })
    return data
  })
}

export async function getSubmission(id: number): Promise<SubmissionDetail> {
  return withApiError(async () => {
    const { data } = await apiClient.get<SubmissionDetail>(`/submissions/${id}`)
    return data
  })
}

export async function fileSubmission(
  input: FileSubmissionInput,
): Promise<SubmissionIngestResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('corporation', input.corporation)
    form.append('as_at', input.as_at)
    form.append('alert_level', input.alert_level)
    if (input.event_id !== undefined) form.append('event_id', String(input.event_id))
    if (input.present_activity) form.append('present_activity', input.present_activity)
    if (input.situation_overview) form.append('situation_overview', input.situation_overview)
    if (input.incidentsFile) form.append('incidents_file', input.incidentsFile)
    if (input.logsFile) form.append('logs_file', input.logsFile)
    const { data } = await apiClient.post<SubmissionIngestResult>('/submissions', form)
    return data
  })
}
