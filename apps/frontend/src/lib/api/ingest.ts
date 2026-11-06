import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { IngestResult } from '@/types/dmcu'

export async function uploadFieldData(file: File): Promise<IngestResult> {
  return withApiError(async () => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await apiClient.post<IngestResult>('/field-data/upload', form)
    return data
  })
}
