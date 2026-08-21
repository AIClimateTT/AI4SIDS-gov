import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { RowErrorsTable } from '@/components/submissions/submission-result'
import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import { formatConstant } from '@/lib/format-constant'
import { submissionQueries } from '@/lib/queries/submissions'

export const Route = createFileRoute('/corp/filings/$submissionId')({
  component: FilingPage,
})

function FilingPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to view this filing." />
    )
  }

  return <FilingPageContent />
}

function FilingPageContent() {
  const { submissionId } = Route.useParams()
  const submissionIdNum = Number(submissionId)
  const submissionQuery = useQuery(submissionQueries.detail(submissionIdNum))

  if (submissionQuery.isError) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Situation report"
          actions={
            <Button variant="outline" render={<Link to="/corp" />}>
              Back to home
            </Button>
          }
        />
        <EmptyState
          title="Could not load this filing"
          description={submissionQuery.error.message}
        />
      </div>
    )
  }

  if (!submissionQuery.data) {
    return <LoadingBlock rows={6} />
  }

  const submission = submissionQuery.data

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Situation Report #${submission.sequence_no}`}
        description={`As at ${new Date(submission.as_at).toLocaleString()} · ${formatConstant(
          submission.alert_level,
        )}`}
        actions={
          submission.event_id != null ? (
            <Button
              variant="outline"
              render={
                <Link
                  to="/corp/events/$eventId"
                  params={{ eventId: String(submission.event_id) }}
                />
              }
            >
              Back to {submission.event_title ?? 'event'}
            </Button>
          ) : (
            <Button variant="outline" render={<Link to="/corp" />}>
              Back to home
            </Button>
          )
        }
      />

      <ContentCard title="Situation">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Present activity</dt>
            <dd>{submission.present_activity || '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Situation overview</dt>
            <dd>{submission.situation_overview || '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Incidents</dt>
            <dd>{submission.incident_count}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Situation logs</dt>
            <dd>{submission.log_count}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Source</dt>
            <dd>{submission.source_file ?? 'Conversation'}</dd>
          </div>
        </dl>
      </ContentCard>

      {submission.row_errors.length > 0 ? (
        <ContentCard title="Rejected rows">
          <RowErrorsTable rowErrors={submission.row_errors} />
        </ContentCard>
      ) : null}
    </div>
  )
}
