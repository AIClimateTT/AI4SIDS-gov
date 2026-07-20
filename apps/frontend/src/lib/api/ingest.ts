import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { IngestModuleName, IngestResult } from '@/types/dmcu'

export async function ingestModule(
  moduleName: IngestModuleName,
  file: File,
  corporation?: string,
): Promise<IngestResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('file', file)
    if (corporation) {
      form.append('corporation', corporation)
    }
    const { data } = await apiClient.post<IngestResult>(
      `/ingest/${moduleName}`,
      form,
    )
    return data
  })
}
