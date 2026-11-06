import type { EventSummary, SubmissionSummary } from '@/types/dmcu'

export type FilingGroup = {
  event: EventSummary | null
  filings: SubmissionSummary[]
}

function time(value: string): number {
  return new Date(value).getTime()
}

/**
 * Filings by event, newest filing first. Events with filings come first, latest
 * activity on top; then events with none; then any filings with no event.
 */
export function groupFilingsByEvent(
  filings: SubmissionSummary[],
  events: EventSummary[],
): FilingGroup[] {
  const newest = [...filings].sort((a, b) => time(b.as_at) - time(a.as_at))
  const known = new Set(events.map((event) => event.id))

  const groups: FilingGroup[] = events.map((event) => ({
    event,
    filings: newest.filter((filing) => filing.event_id === event.id),
  }))
  const latest = (group: FilingGroup) =>
    group.filings.length > 0 ? time(group.filings[0].as_at) : Number.NEGATIVE_INFINITY
  groups.sort((a, b) => {
    const difference = latest(b) - latest(a)
    if (difference !== 0 && Number.isFinite(difference)) return difference
    if (latest(a) !== latest(b)) return latest(a) === Number.NEGATIVE_INFINITY ? 1 : -1
    return time(b.event!.started_at) - time(a.event!.started_at)
  })

  const loose = newest.filter(
    (filing) => filing.event_id === null || !known.has(filing.event_id),
  )
  return loose.length > 0 ? [...groups, { event: null, filings: loose }] : groups
}
