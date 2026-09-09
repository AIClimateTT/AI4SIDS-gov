import { Outlet, createFileRoute, redirect } from '@tanstack/react-router'

import { isAuthenticated } from '@/lib/auth/token'

export const Route = createFileRoute('/_auth')({
  beforeLoad: async () => {
    if (isAuthenticated()) throw redirect({ to: '/' })
  },
  component: AuthLayout,
})

function AuthLayout() {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="w-full max-w-md">
        <Outlet />
      </div>
    </div>
  )
}
