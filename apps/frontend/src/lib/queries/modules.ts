import { queryOptions } from '@tanstack/react-query'

import { getModules } from '@/lib/api/modules'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const moduleKeys = {
  all: () => ['modules'] as const,
  lists: () => [...moduleKeys.all(), 'list'] as const,
  list: () => [...moduleKeys.lists()] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const moduleQueries = {
  list: () =>
    queryOptions({
      queryKey: moduleKeys.list(),
      queryFn: getModules,
    }),
}
