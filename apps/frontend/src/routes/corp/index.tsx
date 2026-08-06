import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { eventQueries } from '@/lib/queries/submissions'
import type { EventSummary } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

export const Route = createFileRoute('/corp/')({
  component: CorpHomePage,
})

function CorpHomePage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <div className="space-y-6">
        <RoleMismatchNotice expected="corp" />
        <p className="text-sm text-muted-foreground">
          Switch to a corporation identity to see your events.
        </p>
      </div>
    )
  }

  return <EventsList identity={identity} />
}

function EventsList({ identity }: { identity: CorpIdentity }) {
  const { data, isPending, isError, error } = useQuery(
    eventQueries.list(identity.corporation),
  )

  const running = data?.filter((event) => event.ended_at === null) ?? []
  const past = data?.filter((event) => event.ended_at !== null) ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title={identityLabel(identity)}
        description="File situation reports and manage your events."
        actions={
          <Button render={<Link to="/corp/events/new" />}>
            <PlusIcon />
            Declare an event
          </Button>
        }
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState title="Could not load events" description={error.message} />
      ) : null}

      {data && data.length === 0 ? (
        <EmptyState
          title="No events yet"
          description="Declare an event to start filing situation reports against it."
          action={
            <Button render={<Link to="/corp/events/new" />}>
              <PlusIcon />
              Declare an event
            </Button>
          }
        />
      ) : null}

      {running.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Running</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {running.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        </div>
      ) : null}

      {past.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Past</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {past.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function EventCard({ event }: { event: EventSummary }) {
  return (
    <Link
      to="/corp/events/$eventId"
      params={{ eventId: String(event.id) }}
      className="block"
    >
      <ContentCard
        title={event.title}
        description={`${formatConstant(event.hazard_type)} · started ${new Date(
          event.started_at,
        ).toLocaleDateString()}`}
      />
    </Link>
  )
}
