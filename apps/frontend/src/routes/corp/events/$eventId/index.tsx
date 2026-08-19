import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { MessageSquareIcon, PlusIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { eventQueries, submissionQueries } from '@/lib/queries/submissions'
import type { SubmissionSummary } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

export const Route = createFileRoute('/corp/events/$eventId/')({
  component: EventPage,
})

function EventPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to view this event." />
    )
  }

  return <EventPageContent identity={identity} />
}

function EventPageContent({ identity }: { identity: CorpIdentity }) {
  const { eventId } = Route.useParams()
  const eventIdNum = Number(eventId)

  const eventsQuery = useQuery(eventQueries.list(identity.corporation))
  const submissionsQuery = useQuery(
    submissionQueries.list({ event_id: eventIdNum }),
  )

  const event = eventsQuery.data?.find((candidate) => candidate.id === eventIdNum)
  const submissions = submissionsQuery.data ?? []
  const latestId = submissions[0]?.id
  const hasLatest = latestId !== undefined
  // Present activity only lives on the detail record — the list endpoint
  // returns summaries without it — so the header needs a second fetch for
  // the single most recent filing. Kept out of the page-wide isPending /
  // isError below: its own pending/error/success states render locally
  // inside "Latest situation" so a failed detail fetch reads as exactly
  // that, not as "no filings yet" or as a whole-page failure that would
  // hide the (already loaded) filings list.
  const latestDetailQuery = useQuery(submissionQueries.detail(latestId ?? 0))
  const latest = latestDetailQuery.data

  const nextSequence =
    submissions.length > 0
      ? Math.max(...submissions.map((submission) => submission.sequence_no)) + 1
      : 1

  const isPending = eventsQuery.isPending || submissionsQuery.isPending
  const isError = eventsQuery.isError || submissionsQuery.isError
  const error = eventsQuery.error ?? submissionsQuery.error

  if (isError) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={event?.title ?? 'Event'}
          actions={
            <Button variant="outline" render={<Link to="/corp" />}>
              Back to events
            </Button>
          }
        />
        <EmptyState
          title="Could not load event"
          description={error?.message ?? 'Unknown error'}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={event?.title ?? 'Event'}
        description={
          event
            ? `${formatConstant(event.hazard_type)} · started ${new Date(
                event.started_at,
              ).toLocaleDateString()}`
            : undefined
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" render={<Link to="/corp" />}>
              Back to events
            </Button>
            {/* sequence_no is backend-assigned; showing a number before the
                filings list has actually loaded would name the wrong report. */}
            {submissionsQuery.isSuccess ? (
              <>
                <Button
                  variant="outline"
                  render={
                    <Link
                      to="/corp/events/$eventId/file"
                      params={{ eventId }}
                    />
                  }
                >
                  <PlusIcon />
                  File CSV #{nextSequence}
                </Button>
                <Button
                  render={
                    <Link
                      to="/corp/events/$eventId/chat"
                      params={{ eventId }}
                    />
                  }
                >
                  <MessageSquareIcon />
                  File by conversation
                </Button>
              </>
            ) : null}
          </div>
        }
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {hasLatest ? (
        <ContentCard title="Latest situation">
          {latestDetailQuery.isPending ? (
            <LoadingBlock rows={2} />
          ) : latestDetailQuery.isError ? (
            <p className="text-sm text-muted-foreground">
              The previous filing could not be loaded.
            </p>
          ) : latest ? (
            <dl className="grid gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Present activity</dt>
                <dd>{latest.present_activity || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Alert level</dt>
                <dd>{formatConstant(latest.alert_level)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">As at</dt>
                <dd>{new Date(latest.as_at).toLocaleString()}</dd>
              </div>
            </dl>
          ) : null}
        </ContentCard>
      ) : null}

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Filings</h2>

        {submissionsQuery.data && submissions.length === 0 ? (
          <EmptyState
            title="No filings yet"
            description="File the first situation report for this event."
            action={
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  render={
                    <Link to="/corp/events/$eventId/file" params={{ eventId }} />
                  }
                >
                  <PlusIcon />
                  File CSV #1
                </Button>
                <Button
                  render={
                    <Link to="/corp/events/$eventId/chat" params={{ eventId }} />
                  }
                >
                  <MessageSquareIcon />
                  File by conversation
                </Button>
              </div>
            }
          />
        ) : null}

        {submissions.length > 0 ? (
          <div className="space-y-2">
            {submissions.map((submission) => (
              <SubmissionRow key={submission.id} submission={submission} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function SubmissionRow({ submission }: { submission: SubmissionSummary }) {
  return (
    <ContentCard
      title={`Situation Report #${submission.sequence_no}`}
      description={`As at ${new Date(submission.as_at).toLocaleString()} · ${formatConstant(
        submission.alert_level,
      )}`}
    >
      <p className="text-sm text-muted-foreground">
        {submission.incident_count} incidents · {submission.log_count} logs
      </p>
    </ContentCard>
  )
}
