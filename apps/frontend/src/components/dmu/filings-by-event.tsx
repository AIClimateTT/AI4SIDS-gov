import { Link } from '@tanstack/react-router'
import { ChevronDownIcon, ChevronRightIcon } from 'lucide-react'
import { useState } from 'react'

import { AlertLevelBadge, EmptyState } from '@/components/shared'
import { TranscriptMenu } from '@/components/dmu/transcript-menu'
import { ContentCard } from '@/components/shared/content-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { AdminCaptureSession } from '@/lib/api/admin-capture'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { groupFilingsByEvent } from '@/lib/group-filings'
import type { EventSummary, SubmissionSummary } from '@/types/dmcu'

/**
 * `captureSessions` is the admin register. Pass it only for admins: it adds a
 * transcript export to filed rows and a "See drafts" panel per event. Drafts
 * show that they exist and can be exported; their contents stay unread here.
 */
export function FilingsByEvent({
  corporation,
  filings,
  events,
  captureSessions,
}: {
  corporation: string
  filings: SubmissionSummary[]
  events: EventSummary[]
  captureSessions?: AdminCaptureSession[]
}) {
  const groups = groupFilingsByEvent(filings, events)
  const knownEvents = new Set(events.map((event) => event.id))
  const drafts = (captureSessions ?? []).filter((session) => session.status === 'draft')
  const sessionBySubmission = new Map(
    (captureSessions ?? [])
      .filter((session) => session.submission_id !== null)
      .map((session) => [session.submission_id as number, session]),
  )
  const draftsFor = (eventId: number | null) =>
    drafts.filter((draft) =>
      eventId === null
        ? draft.event_id === null || !knownEvents.has(draft.event_id)
        : draft.event_id === eventId,
    )
  if (draftsFor(null).length > 0 && !groups.some((group) => group.event === null)) {
    groups.push({ event: null, filings: [] })
  }

  if (filings.length === 0 && events.length === 0 && drafts.length === 0) {
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
            <p className="text-sm text-muted-foreground">
              {group.event ? 'No filings for this event.' : 'No filings without an event.'}
            </p>
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
                        {sessionBySubmission.has(filing.id) ? (
                          <span className="ml-1 inline-block">
                            <TranscriptMenu
                              sessionId={sessionBySubmission.get(filing.id)!.id}
                            />
                          </span>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {captureSessions ? <DraftsPanel drafts={draftsFor(group.event?.id ?? null)} /> : null}
        </ContentCard>
      ))}
    </div>
  )
}

function DraftsPanel({ drafts }: { drafts: AdminCaptureSession[] }) {
  const [open, setOpen] = useState(false)
  if (drafts.length === 0) return null
  const Chevron = open ? ChevronDownIcon : ChevronRightIcon

  return (
    <div className="mt-4 border-t pt-3">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Chevron className="size-3.5" />
        {open ? 'Hide drafts' : `See drafts (${drafts.length})`}
      </Button>
      {open ? (
        <div className="mt-3 rounded-md border border-dashed bg-muted/40 p-3">
          <p className="mb-2 text-xs text-muted-foreground">
            Unfiled conversations. Their incidents and report stay with the officer until filed;
            export the transcript to review how the capture went.
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Opened</TableHead>
                  <TableHead>Last activity</TableHead>
                  <TableHead className="text-right">Officer messages</TableHead>
                  <TableHead>Sitrep</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {drafts.map((draft) => (
                  <TableRow key={draft.id}>
                    <TableCell>
                      <Badge variant="outline" className="mr-2">
                        Draft
                      </Badge>
                      {formatWhen(draft.created_at)}
                    </TableCell>
                    <TableCell>{formatWhen(draft.updated_at)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {draft.officer_message_count}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {draft.has_sitrep ? 'Previewed' : 'Not generated'}
                    </TableCell>
                    <TableCell className="text-right">
                      <TranscriptMenu sessionId={draft.id} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : null}
    </div>
  )
}
