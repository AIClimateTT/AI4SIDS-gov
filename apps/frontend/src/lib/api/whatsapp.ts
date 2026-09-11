import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  WhatsAppBriefingResult,
  WhatsAppConfirmResult,
  WhatsAppDraft,
  WhatsAppDraftSummary,
  WhatsAppDraftUpdate,
  WhatsAppExtractResult,
} from '@/types/dmcu'

export type WhatsAppExtractInput = {
  file?: File
  text?: string
  asAt: string
}

export async function extractWhatsApp(
  input: WhatsAppExtractInput,
): Promise<WhatsAppExtractResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('as_at', input.asAt)
    if (input.file) {
      form.append('file', input.file)
    } else if (input.text) {
      form.append('text', input.text)
    }
    const { data } = await apiClient.post<WhatsAppExtractResult>(
      '/whatsapp/extract',
      form,
    )
    return data
  })
}

export async function listWhatsAppDrafts(): Promise<WhatsAppDraftSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<WhatsAppDraftSummary[]>('/whatsapp/drafts')
    return data
  })
}

export async function getWhatsAppDraft(id: number): Promise<WhatsAppDraft> {
  return withApiError(async () => {
    const { data } = await apiClient.get<WhatsAppDraft>(`/whatsapp/drafts/${id}`)
    return data
  })
}

export async function updateWhatsAppDraft(
  id: number,
  payload: WhatsAppDraftUpdate,
): Promise<WhatsAppDraft> {
  return withApiError(async () => {
    const { data } = await apiClient.put<WhatsAppDraft>(
      `/whatsapp/drafts/${id}`,
      payload,
    )
    return data
  })
}

export async function adjustWhatsAppDraft(
  id: number,
  instruction: string,
): Promise<WhatsAppDraft> {
  return withApiError(async () => {
    const { data } = await apiClient.post<WhatsAppDraft>(
      `/whatsapp/drafts/${id}/adjust`,
      { instruction },
    )
    return data
  })
}

export async function generateWhatsAppBriefing(
  id: number,
): Promise<WhatsAppBriefingResult> {
  return withApiError(async () => {
    const { data } = await apiClient.post<WhatsAppBriefingResult>(
      `/whatsapp/drafts/${id}/briefing`,
    )
    return data
  })
}

export async function promoteWhatsAppDraft(
  id: number,
): Promise<WhatsAppConfirmResult> {
  return withApiError(async () => {
    const { data } = await apiClient.post<WhatsAppConfirmResult>(
      `/whatsapp/drafts/${id}/promote`,
    )
    return data
  })
}
