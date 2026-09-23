import { queryOptions } from '@tanstack/react-query'

import { getIncidents } from '@/lib/api/incidents'
import type { IncidentListParams } from '@/types/dmcu'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const incidentKeys = {
  all: () => ['incidents'] as const,
  lists: () => [...incidentKeys.all(), 'list'] as const,
  list: (params: IncidentListParams = {}) =>
    [...incidentKeys.lists(), params] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const incidentQueries = {
  list: (params: IncidentListParams = {}) =>
    queryOptions({
      queryKey: incidentKeys.list(params),
      queryFn: () => getIncidents(params),
    }),
}
