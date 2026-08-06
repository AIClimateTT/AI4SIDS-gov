import { createFileRoute } from '@tanstack/react-router'

import { EmptyState, PageHeader } from '@/components/shared'

// Placeholder so /corp and /corp/events/new can link here now. Task 5 replaces
// this with the real event page: header from the latest submission, the run
// of filings, and the "File report #{next}" action.
export const Route = createFileRoute('/corp/events/$eventId/')({
  component: EventPage,
})

function EventPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Event"
        description="Situation report filings for this event."
      />
      <EmptyState
        title="Event detail arrives next"
        description="The filing history and report form land in the next release."
      />
    </div>
  )
}
