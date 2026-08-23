import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Composer } from '@/components/corp/composer'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { captureQueries, useCreateCaptureSession } from '@/lib/queries/capture'
import { eventQueries, submissionQueries } from '@/lib/queries/submissions'
import { resolveSitrepHref } from '@/lib/sitrep-href'
import type { EventSummary, SubmissionSummary, CaptureSession } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

export const Route = createFileRoute('/corp/')({
  component: CorpHomePage,
})

function CorpHomePage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to file situation reports." />
    )
  }

  return <CorpHome identity={identity} />
}

function latestSubmissionByEvent(
  submissions: SubmissionSummary[],
): Map<number, SubmissionSummary> {
  const latest = new Map<number, SubmissionSummary>()
  for (const submission of submissions) {
    if (submission.event_id == null) continue
    const current = latest.get(submission.event_id)
    if (!current || new Date(submission.as_at) > new Date(current.as_at)) {
      latest.set(submission.event_id, submission)
    }
  }
  return latest
}

function CorpHome({ identity }: { identity: CorpIdentity }) {
  const navigate = useNavigate()
  const draftsQuery = useQuery(captureQueries.list(identity.corporation))
  const eventsQuery = useQuery(eventQueries.list(identity.corporation))
  const submissionsQuery = useQuery(
    submissionQueries.list({ corporation: identity.corporation }),
  )
  const createSession = useCreateCaptureSession()

  // Drafts are unfinished business, not a catalogue -- show the single most
  // recent one rather than a list.
  const draft = draftsQuery.data
    ?.filter((session) => session.status === 'draft')
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))[0]

  const running = eventsQuery.data?.filter((event) => event.ended_at === null) ?? []
  const submissions = submissionsQuery.data ?? []
  const latestByEvent = latestSubmissionByEvent(submissions)

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8">
      <PageHeader
        title={identityLabel(identity)}
        description="Start a sitrep by describing what is happening. After the first update, confirm the event — the card stays until you do."
      />

      {draft ? (
        <ContentCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm">
              Resume your draft from {new Date(draft.updated_at).toLocaleString()}
            </p>
            <Button
              variant="outline"
              size="sm"
              render={
                <Link to="/corp/c/$sessionId" params={{ sessionId: String(draft.id) }} />
              }
            >
              Resume
            </Button>
          </div>
        </ContentCard>
      ) : null}

      <div className="flex max-w-2xl mx-auto w-full justify-center">
        <Composer
          corporation={identity.corporation}
          createSession={createSession.mutateAsync}
          onStarted={(sessionId, firstMessage) =>
            void navigate({
              to: '/corp/c/$sessionId',
              params: { sessionId: String(sessionId) },
              search: { first: firstMessage },
            })
          }
        />
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Live now</h2>

        {eventsQuery.isPending ? <LoadingBlock rows={2} /> : null}

        {eventsQuery.isError ? (
          <EmptyState
            title="Could not load events"
            description={eventsQuery.error.message}
          />
        ) : null}

        {eventsQuery.isSuccess && running.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No events running right now. Start a sitrep above — you will confirm
            the event in the conversation.
          </p>
        ) : null}

        {running.length > 0 ? (
          <div className="space-y-2">
            {running.map((event) => (
              <LiveEventRow key={event.id} event={event} latest={latestByEvent.get(event.id)} />
            ))}
          </div>
        ) : null}
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Recent filings</h2>

        {submissionsQuery.isPending ? <LoadingBlock rows={4} /> : null}

        {submissionsQuery.isError ? (
          <EmptyState
            title="Could not load submissions"
            description={submissionsQuery.error.message}
          />
        ) : null}

        {submissionsQuery.isSuccess && submissions.length === 0 ? (
          <EmptyState
            title="No submissions yet"
            description="Filed situation reports will appear here."
          />
        ) : null}

        {submissions.length > 0 ? (
          <FilingsTable
            submissions={submissions}
            sessions={draftsQuery.data ?? []}
          />
        ) : null}
      </div>
    </div>
  )
}

function LiveEventRow({
  event,
  latest,
}: {
  event: EventSummary
  latest?: SubmissionSummary
}) {
  return (
    <Link to="/corp/events/$eventId" params={{ eventId: String(event.id) }} className="block">
      <ContentCard
        title={event.title}
        description={`${formatConstant(event.hazard_type)} · started ${new Date(
          event.started_at,
        ).toLocaleDateString()}`}
        action={
          latest ? (
            <Badge variant="secondary">{formatConstant(latest.alert_level)}</Badge>
          ) : null
        }
      >
        <p className="text-sm text-muted-foreground">
          {latest
            ? `${latest.incident_count} incidents · last filed ${new Date(
                latest.as_at,
              ).toLocaleString()}`
            : 'No filings yet'}
        </p>
      </ContentCard>
    </Link>
  )
}

function FilingsTable({
  submissions,
  sessions,
}: {
  submissions: SubmissionSummary[]
  sessions: CaptureSession[]
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>As at</TableHead>
          <TableHead>Event</TableHead>
          <TableHead>Report</TableHead>
          <TableHead>Alert level</TableHead>
          <TableHead>Incidents</TableHead>
          <TableHead>Logs</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
            {submissions.map((submission) => (
              <FilingRow
                key={submission.id}
                submission={submission}
                sessions={sessions}
              />
            ))}
      </TableBody>
    </Table>
  )
}

function FilingRow({
  submission,
  sessions,
}: {
  submission: SubmissionSummary
  sessions: CaptureSession[]
}) {
  const navigate = useNavigate()
  const href = resolveSitrepHref(submission, sessions)
  const goToSitrep = () => void navigate(href)

  return (
    <TableRow className="cursor-pointer" onClick={goToSitrep}>
      <TableCell>{new Date(submission.as_at).toLocaleString()}</TableCell>
      <TableCell>{submission.event_title ?? '—'}</TableCell>
      <TableCell>#{submission.sequence_no}</TableCell>
      <TableCell>{formatConstant(submission.alert_level)}</TableCell>
      <TableCell>{submission.incident_count}</TableCell>
      <TableCell>{submission.log_count}</TableCell>
    </TableRow>
  )
}
