import { Navigate, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import {
  ButtonLink,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { useIdentity } from '@/hooks/use-identity'
import { captureQueries } from '@/lib/queries/capture'
import { submissionQueries } from '@/lib/queries/submissions'
import { resolveSitrepHref } from '@/lib/sitrep-href'

export const Route = createFileRoute('/corp/filings/$submissionId')({
  component: FilingPage,
})

function FilingPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="This account is not a corporation account, so it cannot view this filing." />
    )
  }

  return <FilingRedirect corporation={identity.corporation} />
}

function FilingRedirect({ corporation }: { corporation: string }) {
  const { submissionId } = Route.useParams()
  const submissionIdNum = Number(submissionId)
  const submissionQuery = useQuery(submissionQueries.detail(submissionIdNum))
  const sessionsQuery = useQuery(captureQueries.list(corporation))

  if (submissionQuery.isError) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <PageHeader
          title="Situation report"
          actions={
            <ButtonLink variant="outline" to="/corp">
              Back to home
            </ButtonLink>
          }
        />
        <EmptyState
          title="Could not load this filing"
          description={submissionQuery.error.message}
        />
      </div>
    )
  }

  if (!submissionQuery.data || sessionsQuery.isPending) {
    return <LoadingBlock rows={4} />
  }

  const href = resolveSitrepHref(submissionQuery.data, sessionsQuery.data ?? [])
  if (href.to === '/corp') {
    return <Navigate to="/corp" />
  }
  if (href.to === '/corp/c/$sessionId') {
    return <Navigate to="/corp/c/$sessionId" params={href.params} />
  }
  return <Navigate to="/corp/events/$eventId" params={href.params} />
}
