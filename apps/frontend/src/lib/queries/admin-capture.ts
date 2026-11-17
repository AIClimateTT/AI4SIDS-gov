import { queryOptions } from '@tanstack/react-query'

import { getAdminCaptureSessions } from '@/lib/api/admin-capture'

export const adminCaptureKeys = {
  all: () => ['admin-capture'] as const,
  list: (corporation: string) => [...adminCaptureKeys.all(), 'list', corporation] as const,
}

export const adminCaptureQueries = {
  list: (corporation: string, enabled = true) =>
    queryOptions({
      queryKey: adminCaptureKeys.list(corporation),
      queryFn: () => getAdminCaptureSessions(corporation),
      enabled: enabled && !!corporation,
    }),
}
