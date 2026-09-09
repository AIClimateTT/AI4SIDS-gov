import { Outlet, createFileRoute } from '@tanstack/react-router'

import { requireAuth } from '@/lib/auth/guard'

export const Route = createFileRoute('/corp')({
  beforeLoad: async ({ location }) => {
    await requireAuth({ location })
  },
  component: () => <Outlet />,
})
