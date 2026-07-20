import { queryOptions } from '@tanstack/react-query'

import { getTemplates } from '@/lib/api/templates'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const templateKeys = {
  all: () => ['templates'] as const,
  lists: () => [...templateKeys.all(), 'list'] as const,
  list: () => [...templateKeys.lists()] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const templateQueries = {
  list: () =>
    queryOptions({
      queryKey: templateKeys.list(),
      queryFn: getTemplates,
    }),
}
