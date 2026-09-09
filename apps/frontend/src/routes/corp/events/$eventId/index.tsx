import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { MessageSquareIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  AlertLevelBadge,
  ButtonLink,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { Badge } from '@/components/ui/badge'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { captureQueries, useCreateCaptureSession } from '@/lib/queries/capture'
import { eventQueries, submissionQueries } from '@/lib/queries/submissions'
import type { CaptureSession } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

export const Route = createFileRoute('/corp/events/$eventId/')({
  component: EventPage,
})

function EventPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="This account is not a corporation account, so it cannot view this event." />
    )
  }

  return <EventPageContent identity={identity} />
}

function EventPageContent({ identity }: { identity: CorpIdentity }) {
  const { eventId } = Route.useParams()
  const eventIdNum = Number(eventId)

  const eventsQuery = useQuery(eventQueries.list(identity.corporation))
  const sessionsQuery = useQuery(
    captureQueries.list(identity.corporation, eventIdNum),
  )
  const submissionsQuery = useQuery(
    submissionQueries.list({ event_id: eventIdNum }),
  )

  const event = eventsQuery.data?.find(
    (candidate) => candidate.id === eventIdNum,
  )
  const sessions = (sessionsQuery.data ?? [])
    .slice()
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  const submissions = submissionsQuery.data ?? []
  const latestId = submissions[0]?.id
  const hasLatest = latestId !== undefined
  const latestDetailQuery = useQuery(submissionQueries.detail(latestId ?? 0))
  const latest = latestDetailQuery.data

  const isPending =
    eventsQuery.isPending ||
    sessionsQuery.isPending ||
    submissionsQuery.isPending
  const isError = eventsQuery.isError || sessionsQuery.isError
  const error = eventsQuery.error ?? sessionsQuery.error

  if (isError) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <PageHeader
          title={event?.title ?? 'Event'}
          actions={
            <ButtonLink variant="outline" to="/corp">
              Back to home
            </ButtonLink>
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
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <PageHeader
        title={event?.title ?? 'Event'}
        description={
          event
            ? `${formatConstant(event.hazard_type)} · started ${formatDay(
                event.started_at,
              )}`
            : undefined
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <ButtonLink variant="outline" to="/corp">
              Back to home
            </ButtonLink>
            <StartSitrepButton
              corporation={identity.corporation}
              eventId={eventIdNum}
            />
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
                <dd>
                  <AlertLevelBadge level={latest.alert_level} />
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">As at</dt>
                <dd className="tabular-nums">{formatWhen(latest.as_at)}</dd>
              </div>
            </dl>
          ) : null}
        </ContentCard>
      ) : null}

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Sitreps</h2>

        {sessionsQuery.isSuccess && sessions.length === 0 ? (
          <EmptyState
            title="No sitreps yet"
            description="Start a sitrep to capture this event by conversation."
            action={
              <StartSitrepButton
                corporation={identity.corporation}
                eventId={eventIdNum}
              />
            }
          />
        ) : null}

        {sessions.length > 0 ? (
          <div className="space-y-2">
            {sessions.map((session) => (
              <SitrepRow key={session.id} session={session} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function StartSitrepButton({
  corporation,
  eventId,
}: {
  corporation: string
  eventId: number
}) {
  const createSession = useCreateCaptureSession()
  const navigate = useNavigate()

  return (
    <Button
      disabled={createSession.isPending}
      onClick={() =>
        createSession.mutate(
          { corporation, eventId },
          {
            onSuccess: (session) =>
              void navigate({
                to: '/corp/c/$sessionId',
                params: { sessionId: String(session.id) },
              }),
          },
        )
      }
    >
      <MessageSquareIcon />
      Start new sitrep
    </Button>
  )
}

function SitrepRow({ session }: { session: CaptureSession }) {
  return (
    <Link
      to="/corp/c/$sessionId"
      params={{ sessionId: String(session.id) }}
      className="block"
    >
      <ContentCard
        title={session.status === 'draft' ? 'Draft sitrep' : 'Filed sitrep'}
        description={`Updated ${formatWhen(session.updated_at)}`}
        action={
          <div className="flex items-center gap-2">
            <AlertLevelBadge level={session.alert_level} />
            <Badge
              variant={session.status === 'draft' ? 'outline' : 'secondary'}
            >
              {session.status === 'draft' ? 'Draft' : 'Filed'}
            </Badge>
          </div>
        }
      >
        <p className="text-sm text-muted-foreground">
          {session.incidents.length} incidents · {session.logs.length} logs
        </p>
      </ContentCard>
    </Link>
  )
}
