import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { ModuleInfo } from '@/types/dmcu'

export async function getModules(): Promise<ModuleInfo[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<ModuleInfo[]>('/modules')
    return data
  })
}
