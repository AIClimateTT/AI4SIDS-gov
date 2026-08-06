import { createFileRoute } from '@tanstack/react-router'

import { EmptyState, PageHeader } from '@/components/shared'

// Placeholder so CORP_NAV can link here now. Task 6 replaces this with the
// real flat table of everything this corporation has filed.
export const Route = createFileRoute('/corp/submissions')({
  component: SubmissionsPage,
})

function SubmissionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="My submissions"
        description="Everything this corporation has filed, across all events."
      />
      <EmptyState
        title="Submissions list arrives next"
        description="Your filed situation reports will appear here."
      />
    </div>
  )
}
