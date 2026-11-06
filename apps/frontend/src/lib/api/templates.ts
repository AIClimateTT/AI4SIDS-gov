import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { TemplateInfo } from '@/types/dmcu'

export async function getTemplates(): Promise<TemplateInfo[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<TemplateInfo[]>('/templates')
    return data
  })
}
