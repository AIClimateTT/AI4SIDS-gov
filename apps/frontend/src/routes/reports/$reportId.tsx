import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  MarkdownPreview,
  PageHeader,
  StatusBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { reportQueries } from '@/lib/queries/reports'

export const Route = createFileRoute('/reports/$reportId')({
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
        description="Citation-checked markdown, fact table, and review violations."
        actions={
          <Button variant="outline" render={<Link to="/reports" />}>
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

          <ContentCard title="Parameters">
            <dl className="grid gap-2 sm:grid-cols-2">
              {Object.entries(data.params).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    {key}
                  </dt>
                  <dd className="text-sm font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </ContentCard>

          {data.violations.length > 0 ? (
            <ContentCard
              title="Citation violations"
              description="This report needs review before it can be trusted."
            >
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {data.violations.map((violation, index) => (
                  <li key={`${violation.kind}-${index}`}>
                    <span className="font-medium">{violation.kind}</span>
                    {': '}
                    {violation.detail}
                  </li>
                ))}
              </ul>
            </ContentCard>
          ) : null}

          <ContentCard title="Markdown">
            <MarkdownPreview markdown={data.markdown} />
          </ContentCard>

          <ContentCard title="Fact table">
            <pre className="overflow-x-auto rounded-lg bg-muted/40 p-4 font-mono text-xs">
              {JSON.stringify(data.fact_table, null, 2)}
            </pre>
          </ContentCard>
        </>
      ) : null}
    </div>
  )
}
