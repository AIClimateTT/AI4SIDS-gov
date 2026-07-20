import { queryOptions } from '@tanstack/react-query'

import { getOverview } from '@/lib/api/overview'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const overviewKeys = {
  all: () => ['overview'] as const,
  summary: () => [...overviewKeys.all(), 'summary'] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const overviewQueries = {
  summary: () =>
    queryOptions({
      queryKey: overviewKeys.summary(),
      queryFn: getOverview,
    }),
}
