import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import {
  CitationMarkdown,
  ReportFactTable,
  ViolationsPanel,
} from '@/components/reports'
import { reportQueries } from '@/lib/queries/reports'
import { formatConstant } from '@/lib/format-constant'

export const Route = createFileRoute('/dmu/reports/$reportId')({
  component: ReportDetailPage,
})

function ReportDetailPage() {
  const { reportId } = Route.useParams()
  const { data, isPending, isError, error } = useQuery(
    reportQueries.detail(reportId),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={data ? `Report ${data.id}` : 'Report'}
        description="Citation-checked briefing with linked fact table."
        actions={
          <Button variant="outline" render={<Link to="/dmu/reports" />}>
            Back to reports
          </Button>
        }
      />

      {isPending ? <LoadingBlock rows={6} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load report"
          description={error.message}
        />
      ) : null}

      {data ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={data.status} />
            <span className="text-sm text-muted-foreground">
              {data.template} v{data.template_version}
            </span>
            <span className="text-sm text-muted-foreground">
              {new Date(data.created_at).toLocaleString()}
            </span>
          </div>

          <ContentCard title="Parameters" size="sm">
            <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(data.params).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    {formatConstant(key)}
                  </dt>
                  <dd className="text-sm font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </ContentCard>

          {data.data_requirements.length > 0 ? (
            <ContentCard title="Metrics used" size="sm">
              <ul className="space-y-2 text-sm">
                {data.data_requirements.map((requirement) => (
                  <li
                    key={`${requirement.module}.${requirement.metric}`}
                    className="font-mono"
                  >
                    {requirement.module}.{requirement.metric}
                  </li>
                ))}
              </ul>
            </ContentCard>
          ) : null}

          <ViolationsPanel violations={data.violations} />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <ContentCard
              title="Briefing"
              description="Click a citation marker like [C001] to jump to its fact."
            >
              <CitationMarkdown
                markdown={data.markdown}
                violations={data.violations}
              />
            </ContentCard>

            <ContentCard
              title="Fact table"
              description="Every cited number in the briefing maps to a row below."
            >
              <ReportFactTable factTable={data.fact_table} />
            </ContentCard>
          </div>
        </>
      ) : null}
    </div>
  )
}
