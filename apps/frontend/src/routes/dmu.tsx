import { Outlet, createFileRoute } from '@tanstack/react-router'

import { requireAuth } from '@/lib/auth/guard'

export const Route = createFileRoute('/dmu')({
  beforeLoad: async ({ location }) => {
    await requireAuth({ location })
  },
  component: () => (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <Outlet />
    </div>
  ),
})
