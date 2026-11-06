import { describe, expect, it } from 'vitest'

import { groupFilingsByEvent } from '@/lib/group-filings'
import type { EventSummary, SubmissionSummary } from '@/types/dmcu'

function filing(id: number, asAt: string, eventId: number | null): SubmissionSummary {
  return {
    id,
    corporation: 'arima_borough_corporation',
    event_id: eventId,
    event_title: null,
    as_at: asAt,
    alert_level: 'yellow',
    sequence_no: id,
    incident_count: 0,
    log_count: 0,
  }
}

function event(id: number, startedAt: string): EventSummary {
  return {
    id,
    corporation: 'arima_borough_corporation',
    title: `Event ${id}`,
    hazard_type: 'flood',
    started_at: startedAt,
    ended_at: null,
  } as EventSummary
}

describe('groupFilingsByEvent', () => {
  it('groups filings under their event, newest filing first', () => {
    const groups = groupFilingsByEvent(
      [filing(1, '2026-08-21T10:00:00', 1), filing(2, '2026-08-22T10:00:00', 1)],
      [event(1, '2026-08-21T00:00:00')],
    )

    expect(groups).toHaveLength(1)
    expect(groups[0].event?.id).toBe(1)
    expect(groups[0].filings.map((f) => f.id)).toEqual([2, 1])
  })

  it('puts the event with the most recent filing first', () => {
    const groups = groupFilingsByEvent(
      [filing(1, '2026-08-21T10:00:00', 1), filing(2, '2026-11-04T10:00:00', 2)],
      [event(1, '2026-08-21T00:00:00'), event(2, '2026-01-01T00:00:00')],
    )

    expect(groups.map((g) => g.event?.id)).toEqual([2, 1])
  })

  it('keeps an event with no filings, after those that have them', () => {
    const groups = groupFilingsByEvent(
      [filing(1, '2026-08-21T10:00:00', 1)],
      [event(2, '2026-09-01T00:00:00'), event(1, '2026-08-21T00:00:00')],
    )

    expect(groups.map((g) => g.event?.id)).toEqual([1, 2])
    expect(groups[1].filings).toEqual([])
  })

  it('puts filings with no event in a final group', () => {
    const groups = groupFilingsByEvent(
      [filing(1, '2026-11-01T10:00:00', null), filing(2, '2026-08-21T10:00:00', 1)],
      [event(1, '2026-08-21T00:00:00')],
    )

    expect(groups.at(-1)?.event).toBeNull()
    expect(groups.at(-1)?.filings.map((f) => f.id)).toEqual([1])
  })

  it('returns nothing when there is nothing', () => {
    expect(groupFilingsByEvent([], [])).toEqual([])
  })
})
