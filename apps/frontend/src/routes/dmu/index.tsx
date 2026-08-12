import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ContentCard } from '@/components/shared/content-card'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { formatConstant } from '@/lib/format-constant'
import { overviewQueries } from '@/lib/queries/overview'
import { submissionQueries } from '@/lib/queries/submissions'
import { deriveWhoReported } from '@/lib/who-reported'

export const Route = createFileRoute('/dmu/')({ component: OverviewPage })

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function defaultWindow(): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - 30)
  return { from: isoDate(from), to: isoDate(to) }
}

function OverviewPage() {
  const { data, isPending, isError, error } = useQuery(overviewQueries.summary())

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Status of ingested incident data and recent cited briefings."
        actions={
          <>
            <Button variant="outline" render={<Link to="/dmu/field-data" />}>
              <UploadIcon />
              Field data
            </Button>
            <Button render={<Link to="/dmu/reports/new" />}>
              <FileTextIcon />
              Generate report
            </Button>
          </>
        }
      />

      <RoleMismatchNotice expected="dmu" />

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
              <Button variant="outline" size="sm" render={<Link to="/dmu/reports" />}>
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
                              to="/dmu/reports/$reportId"
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

          <WhoHasReportedCard />
        </>
      ) : null}
    </div>
  )
}

function WhoHasReportedCard() {
  const [range, setRange] = useState(defaultWindow)

  const { data, isPending, isError, error } = useQuery(
    submissionQueries.list({ date_from: range.from, date_to: range.to }),
  )

  const rows = useMemo(() => deriveWhoReported(data ?? []), [data])

  return (
    <ContentCard
      title="Who has reported"
      description="Every corporation, across the selected window — corporations that filed nothing still get a row."
      action={
        <div className="flex items-center gap-2">
          <Label htmlFor="who-reported-from" className="sr-only">
            From
          </Label>
          <Input
            id="who-reported-from"
            type="date"
            className="w-auto"
            value={range.from}
            max={range.to}
            onChange={(event) =>
              setRange((prev) => ({ ...prev, from: event.target.value }))
            }
          />
          <span className="text-sm text-muted-foreground">to</span>
          <Label htmlFor="who-reported-to" className="sr-only">
            To
          </Label>
          <Input
            id="who-reported-to"
            type="date"
            className="w-auto"
            value={range.to}
            min={range.from}
            onChange={(event) =>
              setRange((prev) => ({ ...prev, to: event.target.value }))
            }
          />
        </div>
      }
    >
      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load submissions"
          description={error.message}
        />
      ) : null}

      {data ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Corporation</TableHead>
              <TableHead>As at</TableHead>
              <TableHead>Alert level</TableHead>
              <TableHead>Incidents</TableHead>
              <TableHead>Logs</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.corporation}>
                <TableCell className="font-medium">{row.label}</TableCell>
                {row.latest ? (
                  <>
                    <TableCell>
                      {new Date(row.latest.as_at).toLocaleString()}
                    </TableCell>
                    <TableCell>{formatConstant(row.latest.alert_level)}</TableCell>
                    <TableCell>{row.latest.incident_count}</TableCell>
                    <TableCell>{row.latest.log_count}</TableCell>
                  </>
                ) : (
                  <TableCell colSpan={4} className="text-muted-foreground">
                    No reports at this time
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </ContentCard>
  )
}
