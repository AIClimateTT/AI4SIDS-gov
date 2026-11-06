import { queryOptions } from '@tanstack/react-query'

import { getTemplates } from '@/lib/api/templates'

export const templateKeys = {
  all: () => ['templates'] as const,
  list: () => [...templateKeys.all(), 'list'] as const,
}

export const templateQueries = {
  list: () =>
    queryOptions({
      queryKey: templateKeys.list(),
      queryFn: getTemplates,
    }),
}
