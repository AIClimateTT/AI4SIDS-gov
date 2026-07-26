import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type {
  CreateTemplateVersionInput,
  TemplateInfo,
  TemplateVersionSummary,
} from '@/types/dmcu'

export async function getTemplates(): Promise<TemplateInfo[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<TemplateInfo[]>('/templates')
    return data
  })
}

export async function getTemplateVersions(
  name: string,
): Promise<TemplateVersionSummary[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<TemplateVersionSummary[]>(
      `/templates/${encodeURIComponent(name)}/versions`,
    )
    return data
  })
}

export async function getTemplateVersion(
  name: string,
  version: number,
): Promise<TemplateInfo> {
  return withApiError(async () => {
    const { data } = await apiClient.get<TemplateInfo>(
      `/templates/${encodeURIComponent(name)}/versions/${version}`,
    )
    return data
  })
}

export async function createTemplateVersion(
  payload: CreateTemplateVersionInput,
): Promise<TemplateInfo> {
  return withApiError(async () => {
    const { data } = await apiClient.post<TemplateInfo>('/templates', payload)
    return data
  })
}
