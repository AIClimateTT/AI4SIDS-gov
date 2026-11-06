import { Link } from '@tanstack/react-router'

import { AlertLevelBadge, EmptyState } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { groupFilingsByEvent } from '@/lib/group-filings'
import type { EventSummary, SubmissionSummary } from '@/types/dmcu'

export function FilingsByEvent({
  corporation,
  filings,
  events,
}: {
  corporation: string
  filings: SubmissionSummary[]
  events: EventSummary[]
}) {
  const groups = groupFilingsByEvent(filings, events)

  if (filings.length === 0 && events.length === 0) {
    return (
      <EmptyState
        title="No filings"
        description="This corporation has filed nothing yet. That's a gap to chase, not a report of no incidents."
      />
    )
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <ContentCard
          key={group.event?.id ?? 'no-event'}
          // Event titles can be a whole sentence of officer text.
          title={
            <span className="line-clamp-2" title={group.event?.title}>
              {group.event?.title ?? 'No event'}
            </span>
          }
          description={
            group.event
              ? [
                  formatConstant(group.event.hazard_type),
                  `Started ${formatDay(group.event.started_at)}`,
                  group.event.ended_at ? `Ended ${formatDay(group.event.ended_at)}` : 'Running',
                ]
                  .filter(Boolean)
                  .join(' · ')
              : undefined
          }
        >
          {group.filings.length === 0 ? (
            <p className="text-sm text-muted-foreground">No filings for this event.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[64px]">No.</TableHead>
                    <TableHead>As at</TableHead>
                    <TableHead>Alert level</TableHead>
                    <TableHead className="text-right">Incidents</TableHead>
                    <TableHead className="text-right">Logs</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {group.filings.map((filing) => (
                    <TableRow key={filing.id}>
                      <TableCell className="tabular-nums">#{filing.sequence_no}</TableCell>
                      <TableCell>{formatWhen(filing.as_at)}</TableCell>
                      <TableCell>
                        <AlertLevelBadge level={filing.alert_level} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {filing.incident_count}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{filing.log_count}</TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        <Link
                          className="text-sm underline"
                          to="/dmu/corporations/$corporation"
                          params={{ corporation }}
                          search={{ tab: 'incidents', submission_id: filing.id }}
                        >
                          Records
                        </Link>
                        {filing.report_id ? (
                          <Link
                            className="ml-3 text-sm underline"
                            to="/dmu/reports/$reportId"
                            params={{ reportId: filing.report_id }}
                          >
                            Report
                          </Link>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </ContentCard>
      ))}
    </div>
  )
}
