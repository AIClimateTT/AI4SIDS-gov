import { Outlet, createFileRoute } from '@tanstack/react-router'

import { requireAuth } from '@/lib/auth/guard'

export const Route = createFileRoute('/dmu')({
  beforeLoad: async ({ location }) => {
    await requireAuth({ location })
  },
  component: () => (
    <div className="w-full space-y-6 lg:p-2">
      <Outlet />
    </div>
  ),
})
