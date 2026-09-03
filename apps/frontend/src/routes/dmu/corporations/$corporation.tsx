import { createFileRoute, notFound } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertLevelBadge, ButtonLink, EmptyState, LoadingBlock, PageHeader, StatCard } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { AlertTrajectory } from '@/components/dmu/alert-trajectory'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { submissionQueries, eventQueries } from '@/lib/queries/submissions'
import { CORPORATION_LABELS, isCanonicalCorporation } from '@/lib/corporations'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'

export const Route = createFileRoute('/dmu/corporations/$corporation')({
  component: CorporationPage,
  // A slug outside the fourteen is a 404, not an empty page. An unknown
  // corporation matches no rows, and a page of zeroes for a region that may
  // have filed plenty reads as an authoritative "nothing happened" — the same
  // failure POST /reports guards against server-side.
  beforeLoad: ({ params }) => {
    if (!isCanonicalCorporation(params.corporation)) throw notFound()
  },
})

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function defaultWindow(): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - 30)
  return { from: isoDate(from), to: isoDate(to) }
}

function CorporationPage() {
  const { corporation } = Route.useParams()
  const [range, setRange] = useState(defaultWindow)

  const label = isCanonicalCorporation(corporation)
    ? CORPORATION_LABELS[corporation]
    : corporation

  const submissions = useQuery(
    submissionQueries.list({
      corporation,
      date_from: range.from,
      date_to: range.to,
    }),
  )
  const events = useQuery(eventQueries.list(corporation))

  // Newest first for the table; the trajectory reverses it, because a reader
  // scanning history wants the latest at the top and a reader following a
  // sequence of alert states wants it left to right in time order.
  const rows = useMemo(
    () =>
      [...(submissions.data ?? [])].sort(
        (a, b) => new Date(b.as_at).getTime() - new Date(a.as_at).getTime(),
      ),
    [submissions.data],
  )

  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, row) => ({
          incidents: acc.incidents + row.incident_count,
          logs: acc.logs + row.log_count,
        }),
        { incidents: 0, logs: 0 },
      ),
    [rows],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={label}
        description="Everything this corporation filed in the selected window."
        actions={
          <ButtonLink variant="outline" to="/dmu">
            Back to overview
          </ButtonLink>
        }
      />

      <div className="flex flex-wrap items-end gap-2">
        <div className="grid gap-1.5">
          <Label htmlFor="corp-from" className="text-xs">
            From
          </Label>
          <Input
            id="corp-from"
            type="date"
            className="w-auto"
            value={range.from}
            max={range.to}
            onChange={(event) =>
              setRange((prev) => ({ ...prev, from: event.target.value }))
            }
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="corp-to" className="text-xs">
            To
          </Label>
          <Input
            id="corp-to"
            type="date"
            className="w-auto"
            value={range.to}
            min={range.from}
            onChange={(event) =>
              setRange((prev) => ({ ...prev, to: event.target.value }))
            }
          />
        </div>
      </div>

      {submissions.isPending ? <LoadingBlock rows={4} /> : null}

      {submissions.isError ? (
        <EmptyState
          title="Could not load submissions"
          description={submissions.error.message}
        />
      ) : null}

      {submissions.data ? (
        rows.length === 0 ? (
          <EmptyState
            title="No reports at this time"
            description="This corporation filed nothing in the selected window. That is a gap to chase, not a report of no incidents."
          />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {/* Safe to index: this branch only renders when rows is
                  non-empty, and the empty case is handled above. */}
              <StatCard
                label="Current alert level"
                value={formatConstant(rows[0].alert_level)}
                hint={`As at ${formatWhen(rows[0].as_at)}`}
              />
              <StatCard
                label="Submissions"
                value={rows.length}
                hint="Filings in this window"
              />
              <StatCard
                label="Incidents"
                value={totals.incidents}
                hint="Across all filings"
              />
              <StatCard
                label="Situation logs"
                value={totals.logs}
                hint="Across all filings"
              />
            </div>

            <ContentCard
              title="Alert level over time"
              description="Oldest first. Each block is one filing, coloured by the level recorded as at that moment."
            >
              <AlertTrajectory submissions={[...rows].reverse()} />
            </ContentCard>

            <ContentCard
              title="Filing history"
              description="Most recent first."
            >
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[64px]">#</TableHead>
                      <TableHead>As at</TableHead>
                      <TableHead>Event</TableHead>
                      <TableHead>Alert level</TableHead>
                      <TableHead className="text-right">Incidents</TableHead>
                      <TableHead className="text-right">Logs</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell className="font-mono text-xs tabular-nums">
                          {row.sequence_no}
                        </TableCell>
                        <TableCell>
                          {formatWhen(row.as_at)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {row.event_title ?? (
                            <span className="italic">No event</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <AlertLevelBadge level={row.alert_level} />
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.incident_count}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.log_count}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </ContentCard>
          </>
        )
      ) : null}

      {events.data && events.data.length > 0 ? (
        <ContentCard
          title="Events"
          description="Hazard events this corporation owns. An event with no end date is still running."
        >
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Hazard</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Ended</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.data.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-medium">{event.title}</TableCell>
                    <TableCell>{formatConstant(event.hazard_type)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDay(event.started_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {event.ended_at ? (
                        formatDay(event.ended_at)
                      ) : (
                        <span className="italic">Still running</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </ContentCard>
      ) : null}
    </div>
  )
}
