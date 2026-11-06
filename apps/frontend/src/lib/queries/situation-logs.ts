import { queryOptions } from '@tanstack/react-query'

import { getSituationLogs } from '@/lib/api/situation-logs'
import type { SituationLogListParams } from '@/types/dmcu'

export const situationLogKeys = {
  all: () => ['situation-logs'] as const,
  list: (params: SituationLogListParams = {}) =>
    [...situationLogKeys.all(), 'list', params] as const,
}

export const situationLogQueries = {
  list: (params: SituationLogListParams = {}) =>
    queryOptions({
      queryKey: situationLogKeys.list(params),
      queryFn: () => getSituationLogs(params),
    }),
}
