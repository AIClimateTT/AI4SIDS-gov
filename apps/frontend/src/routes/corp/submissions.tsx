import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { submissionQueries } from '@/lib/queries/submissions'
import type { SubmissionSummary } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

// Task 4's placeholder held this path in the route tree so CORP_NAV's Link
// `to` union would typecheck. This is the real flat table of everything the
// corporation has filed, across all events.
export const Route = createFileRoute('/corp/submissions')({
  component: SubmissionsPage,
})

function SubmissionsPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to see your submissions." />
    )
  }

  return <SubmissionsList identity={identity} />
}

function SubmissionsList({ identity }: { identity: CorpIdentity }) {
  const { data, isPending, isError, error } = useQuery(
    submissionQueries.list({ corporation: identity.corporation }),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="My submissions"
        description="Everything this corporation has filed, across all events."
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load submissions"
          description={error.message}
        />
      ) : null}

      {data && data.length === 0 ? (
        <EmptyState
          title="No submissions yet"
          description="Filed situation reports will appear here."
        />
      ) : null}

      {data && data.length > 0 ? <SubmissionsTable submissions={data} /> : null}
    </div>
  )
}

function SubmissionsTable({ submissions }: { submissions: SubmissionSummary[] }) {
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
          <TableRow key={submission.id}>
            <TableCell>{new Date(submission.as_at).toLocaleString()}</TableCell>
            <TableCell>{submission.event_title ?? '—'}</TableCell>
            <TableCell>#{submission.sequence_no}</TableCell>
            <TableCell>{formatConstant(submission.alert_level)}</TableCell>
            <TableCell>{submission.incident_count}</TableCell>
            <TableCell>{submission.log_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
