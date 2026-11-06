import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { WhoHasReported, windowPhrase } from '@/components/dmu/who-has-reported'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { ReportTypeBadge } from '@/components/reports/report-type-badge'
import {
  AlertLevelBadge,
  ButtonLink,
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatCard,
  StatusBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { formatWhen } from '@/lib/format-when'
import { overviewQueries } from '@/lib/queries/overview'
import { submissionQueries } from '@/lib/queries/submissions'
import { deriveWhoReported, highestAlert } from '@/lib/who-reported'
import type { ReportingWindowHours } from '@/lib/who-reported'

export const Route = createFileRoute('/dmu/')({ component: DashboardPage })

function DashboardPage() {
  const overview = useQuery(overviewQueries.summary())
  const filings = useQuery(submissionQueries.list({}))
  const [windowHours, setWindowHours] = useState<ReportingWindowHours>(24)
  const now = useMemo(() => new Date(), [filings.dataUpdatedAt])

  const { rows, reportedCount } = useMemo(
    () => deriveWhoReported(filings.data ?? [], now, windowHours),
    [filings.data, now, windowHours],
  )
  const worst = highestAlert(rows)
  const data = overview.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Who has reported, and the latest reports."
      />

      <RoleMismatchNotice expected="dmu" />

      {overview.isPending ? <LoadingBlock rows={4} /> : null}

      {overview.isError ? (
        <EmptyState
          title="Could not load the dashboard"
          description={overview.error.message}
        />
      ) : null}

      {data ? (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                label="Reporting"
                value={`${reportedCount} of ${rows.length}`}
                hint={`In ${windowPhrase(windowHours)}`}
              />
              <Link
                to="/dmu/reports"
                search={{ status: 'needs_review' }}
                className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <StatCard
                  label="Reports to review"
                  value={data.needs_review_count}
                  hint={data.needs_review_count > 0 ? 'Open the list' : 'Nothing waiting'}
                />
              </Link>
              <StatCard
                label="Highest alert"
                value={
                  worst?.latest ? (
                    <AlertLevelBadge level={worst.latest.alert_level} />
                  ) : (
                    'None'
                  )
                }
                hint={worst?.label ?? 'No filings in this period'}
              />
            </div>

            <ContentCard
              title="Recent reports"
              action={
                <ButtonLink variant="outline" size="sm" to="/dmu/reports">
                  View all
                </ButtonLink>
              }
            >
              {data.recent_reports.length === 0 ? (
                <EmptyState
                  title="No reports yet"
                  description="Reports will appear here once they are generated or filed."
                />
              ) : (
                <ul className="divide-y">
                  {data.recent_reports.map((report) => (
                    <li key={report.id} className="space-y-1 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Link
                          to="/dmu/reports/$reportId"
                          params={{ reportId: report.id }}
                          className="text-sm font-medium underline-offset-4 hover:underline"
                        >
                          {report.title}
                        </Link>
                        <StatusBadge status={report.status} />
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <ReportTypeBadge kind={report.kind} verified={report.verified} />
                        {report.period ? <span>{report.period}</span> : null}
                        <span>{formatWhen(report.created_at)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </ContentCard>
          </div>

          {filings.isError ? (
            <EmptyState title="Could not load filings" description={filings.error.message} />
          ) : (
            <WhoHasReported
              rows={rows}
              reportedCount={reportedCount}
              windowHours={windowHours}
              onWindowChange={setWindowHours}
              now={now}
            />
          )}
        </div>
      ) : null}
    </div>
  )
}
