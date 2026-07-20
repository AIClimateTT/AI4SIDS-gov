import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { FileTextIcon, UploadIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatCard,
  StatusBadge,
} from '@/components/shared'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ContentCard } from '@/components/shared/content-card'
import { overviewQueries } from '@/lib/queries/overview'

export const Route = createFileRoute('/')({ component: OverviewPage })

function OverviewPage() {
  const { data, isPending, isError, error } = useQuery(overviewQueries.summary())

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Status of ingested incident data and recent cited briefings."
        actions={
          <>
            <Button variant="outline" render={<Link to="/ingest" />}>
              <UploadIcon />
              Ingest data
            </Button>
            <Button render={<Link to="/reports/new" />}>
              <FileTextIcon />
              Generate report
            </Button>
          </>
        }
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load overview"
          description={error.message}
        />
      ) : null}

      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Survey123 incidents"
              value={data.incident_count_survey123}
              hint="Loaded field assessments"
            />
            <StatCard
              label="SITREP incidents"
              value={data.incident_count_sitreps}
              hint="Corporation situation reports"
            />
            <StatCard
              label="Reports"
              value={data.report_count}
              hint={`${data.needs_review_count} need review`}
            />
            <StatCard
              label="API"
              value={isError ? 'down' : 'connected'}
              hint="Live backend responses"
            />
          </div>

          <ContentCard
            title="Recent reports"
            description="Latest generated briefings"
            action={
              <Button variant="outline" size="sm" render={<Link to="/reports" />}>
                View all
              </Button>
            }
          >
            {data.recent_reports.length === 0 ? (
              <EmptyState
                title="No reports yet"
                description="Generate a briefing from a template to see it here."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Template</TableHead>
                    <TableHead>Params</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Open</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recent_reports.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell>
                        <StatusBadge status={report.status} />
                      </TableCell>
                      <TableCell className="font-medium">
                        {report.template}
                        <span className="ml-1 text-muted-foreground">
                          v{report.template_version}
                        </span>
                      </TableCell>
                      <TableCell className="max-w-[220px] truncate text-muted-foreground">
                        {Object.entries(report.params)
                          .map(([key, value]) => `${key}=${value}`)
                          .join(', ')}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(report.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          render={
                            <Link
                              to="/reports/$reportId"
                              params={{ reportId: report.id }}
                            />
                          }
                        >
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ContentCard>
        </>
      ) : null}
    </div>
  )
}
