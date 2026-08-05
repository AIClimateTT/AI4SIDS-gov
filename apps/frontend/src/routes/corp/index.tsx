import { createFileRoute } from '@tanstack/react-router'

import { EmptyState, PageHeader } from '@/components/shared'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'

export const Route = createFileRoute('/corp/')({
  component: CorpHomePage,
})

function CorpHomePage() {
  const { identity } = useIdentity()
  const title = identity?.role === 'corp' ? identityLabel(identity) : 'My corporation'

  return (
    <div className="space-y-6">
      <PageHeader
        title={title}
        description="File situation reports and manage your events."
      />
      <RoleMismatchNotice expected="corp" />
      <EmptyState
        title="Nothing here yet"
        description="Events and report filing arrive in the next release. Your submissions will appear on this page."
      />
    </div>
  )
}
