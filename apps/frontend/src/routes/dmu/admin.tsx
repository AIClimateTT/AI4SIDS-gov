import { Outlet, createFileRoute } from '@tanstack/react-router'

import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { useIdentity } from '@/hooks/use-identity'
import { isAdmin } from '@/lib/identity'

export const Route = createFileRoute('/dmu/admin')({
  component: AdminLayout,
})

function AdminLayout() {
  const { identity } = useIdentity()
  if (!isAdmin(identity)) {
    return <RoleMismatchNotice expected="admin" />
  }
  return <Outlet />
}
