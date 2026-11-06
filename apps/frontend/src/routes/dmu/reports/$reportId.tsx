import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { ReportView } from '@/components/reports/report-view'
import { EmptyState, LoadingBlock } from '@/components/shared'
import { reportQueries } from '@/lib/queries/reports'

export const Route = createFileRoute('/dmu/reports/$reportId')({
  component: ReportDetailPage,
})

function ReportDetailPage() {
  const { reportId } = Route.useParams()
  const { data, isPending, isError, error } = useQuery(reportQueries.detail(reportId))

  if (isPending) return <LoadingBlock rows={6} />
  if (isError) {
    return <EmptyState title="Could not load report" description={error.message} />
  }
  return <ReportView report={data} />
}
