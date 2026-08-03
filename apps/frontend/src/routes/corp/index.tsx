import { createFileRoute } from '@tanstack/react-router'

import { EmptyState, PageHeader } from '@/components/shared'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'

export const Route = createFileRoute('/corp/')({
  component: CorpHomePage,
})

function CorpHomePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="My corporation"
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
