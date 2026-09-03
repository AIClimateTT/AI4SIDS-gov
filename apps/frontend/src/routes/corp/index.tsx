import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Composer } from '@/components/corp/composer'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import {
  AlertLevelBadge,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
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
import { formatDay, formatWhen } from '@/lib/format-when'
import { captureQueries, useCreateCaptureSession } from '@/lib/queries/capture'
import { eventQueries, submissionQueries } from '@/lib/queries/submissions'
import type {
  CaptureSession,
  EventSummary,
  SubmissionSummary,
} from '@/types/dmcu'

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

  const running =
    eventsQuery.data?.filter((event) => event.ended_at === null) ?? []
  const submissions = submissionsQuery.data ?? []
  const latestByEvent = latestSubmissionByEvent(submissions)

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8">
      <PageHeader
        title={identityLabel(identity)}
        description="Start a sitrep by describing what is happening. After the first update, confirm the event — the card stays until you do."
      />

      {draft ? <DraftCard draft={draft} /> : null}

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
              <LiveEventRow
                key={event.id}
                event={event}
                latest={latestByEvent.get(event.id)}
              />
            ))}
          </div>
        ) : null}
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          Recent filings
        </h2>

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
          <FilingsTable submissions={submissions} />
        ) : null}
      </div>
    </div>
  )
}

/**
 * The unfinished sitrep, if there is one.
 *
 * This is the single most actionable thing on the page — work the officer
 * started and has not filed — and it rendered as an unlabelled card holding one
 * grey sentence, indistinguishable from chrome. It now says what it is, what is
 * already in it, and how far behind it has fallen, so the decision to resume or
 * ignore can be made without opening it.
 */
function DraftCard({ draft }: { draft: CaptureSession }) {
  const captured =
    draft.incidents.length === 0 && draft.logs.length === 0
      ? 'Nothing captured yet'
      : `${draft.incidents.length} incidents · ${draft.logs.length} logs`

  return (
    <ContentCard
      title="Unfiled draft"
      description={`Last edited ${formatWhen(draft.updated_at)}`}
      action={
        <Button
          variant="outline"
          size="sm"
          render={
            <Link
              to="/corp/c/$sessionId"
              params={{ sessionId: String(draft.id) }}
            />
          }
        >
          Resume
        </Button>
      }
    >
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <AlertLevelBadge level={draft.alert_level} />
        <span>{captured}</span>
      </div>
    </ContentCard>
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
    <Link
      to="/corp/events/$eventId"
      params={{ eventId: String(event.id) }}
      className="block"
    >
      <ContentCard
        title={event.title}
        description={`${formatConstant(event.hazard_type)} · started ${formatDay(
          event.started_at,
        )}`}
        action={latest ? <AlertLevelBadge level={latest.alert_level} /> : null}
      >
        <p className="text-sm text-muted-foreground">
          {latest
            ? `${latest.incident_count} incidents · last filed ${formatWhen(latest.as_at)}`
            : 'No filings yet'}
        </p>
      </ContentCard>
    </Link>
  )
}

function FilingsTable({ submissions }: { submissions: SubmissionSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>As at</TableHead>
            <TableHead>Event</TableHead>
            <TableHead className="w-[80px]">Report</TableHead>
            <TableHead className="w-[140px]">Alert level</TableHead>
            {/* Counts are compared down the column, so they are right-aligned
                and tabular — ragged left edges make two- and three-digit
                figures read as the same magnitude. */}
            <TableHead className="w-[100px] text-right">Incidents</TableHead>
            <TableHead className="w-[80px] text-right">Logs</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {submissions.map((submission) => (
            <FilingRow key={submission.id} submission={submission} />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function FilingRow({ submission }: { submission: SubmissionSummary }) {
  return (
    /*
      The row used to be a bare `<tr onClick>`: not focusable, no keydown
      handler, no role. An officer working by keyboard could not open a filing
      at all, and nothing told a screen reader the row led anywhere.

      A real link in the identifying cell fixes that without inventing row
      semantics the table does not have, and it gives each filing a URL that can
      be copied or opened in a new tab. It points at the filing route rather
      than at a resolved destination because which sitrep a submission belongs
      to is a lookup, and that route already owns it.

      `relative` on the row plus `after:absolute inset-0` on the link stretches
      the hit area across the whole row, so it stays a one-click target for the
      mouse while remaining a single tab stop. Positioning a `<tr>` was long
      unreliable and is the reason this pattern is usually written with a click
      handler instead; verified by hit-testing the far edge of the row here.
    */
    <TableRow className="relative transition-colors hover:bg-muted/50 has-[a:focus-visible]:bg-muted/50">
      <TableCell className="font-medium">
        <Link
          to="/corp/filings/$submissionId"
          params={{ submissionId: String(submission.id) }}
          // ring rather than outline: every other focusable thing in the app
          // uses ring-ring/50, and a lone outline would read as a different
          // kind of control.
          className="rounded-sm hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-hidden after:absolute after:inset-0"
        >
          {formatWhen(submission.as_at)}
        </Link>
      </TableCell>
      <TableCell className="text-muted-foreground">
        {submission.event_title ?? '—'}
      </TableCell>
      <TableCell className="tabular-nums">#{submission.sequence_no}</TableCell>
      <TableCell>
        <AlertLevelBadge level={submission.alert_level} />
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {submission.incident_count}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {submission.log_count}
      </TableCell>
    </TableRow>
  )
}
