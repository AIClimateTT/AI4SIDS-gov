import { describe, expect, it } from 'vitest'

import { CANONICAL_CORPORATIONS, CORPORATION_LABELS } from '@/lib/corporations'
import { deriveWhoReported } from '@/lib/who-reported'
import type { SubmissionSummary } from '@/types/dmcu'

function submission(overrides: Partial<SubmissionSummary>): SubmissionSummary {
  return {
    id: 1,
    corporation: 'arima_borough_corporation',
    event_id: null,
    event_title: null,
    as_at: '2023-06-01T00:00:00Z',
    alert_level: 'green',
    sequence_no: 1,
    incident_count: 0,
    log_count: 0,
    ...overrides,
  }
}

describe('deriveWhoReported', () => {
  it('returns one row per canonical corporation when nothing was filed', () => {
    const rows = deriveWhoReported([])

    expect(rows).toHaveLength(CANONICAL_CORPORATIONS.length)
    expect(rows.every((row) => row.latest === null)).toBe(true)
    expect(rows.map((row) => row.corporation).sort()).toEqual(
      [...CANONICAL_CORPORATIONS].sort(),
    )
  })

  it('uses the display label from CORPORATION_LABELS', () => {
    const rows = deriveWhoReported([])
    const arima = rows.find(
      (row) => row.corporation === 'arima_borough_corporation',
    )

    expect(arima?.label).toBe(CORPORATION_LABELS.arima_borough_corporation)
  })

  it('picks the latest submission per corporation regardless of input order', () => {
    const early = submission({
      id: 1,
      corporation: 'arima_borough_corporation',
      as_at: '2023-06-01T00:00:00Z',
      sequence_no: 1,
    })
    const late = submission({
      id: 2,
      corporation: 'arima_borough_corporation',
      as_at: '2023-06-15T00:00:00Z',
      sequence_no: 2,
    })

    const rows = deriveWhoReported([late, early])
    const arima = rows.find(
      (row) => row.corporation === 'arima_borough_corporation',
    )
    expect(arima?.latest?.id).toBe(2)

    const rowsReversed = deriveWhoReported([early, late])
    const arimaReversed = rowsReversed.find(
      (row) => row.corporation === 'arima_borough_corporation',
    )
    expect(arimaReversed?.latest?.id).toBe(2)
  })

  it('sorts reported corporations before unreported ones', () => {
    const rows = deriveWhoReported([
      submission({ corporation: 'siparia_regional_corporation' }),
    ])

    const reportedIndex = rows.findIndex(
      (row) => row.corporation === 'siparia_regional_corporation',
    )
    expect(reportedIndex).toBe(0)
    expect(rows.slice(1).every((row) => row.latest === null)).toBe(true)
  })

  it('preserves canonical order within the unreported group', () => {
    const rows = deriveWhoReported([])
    expect(rows.map((row) => row.corporation)).toEqual(CANONICAL_CORPORATIONS)
  })

  it('sorts the most severe alert level first', () => {
    // The reason this ordering exists: an officer opening the console during an
    // event is answering "where is it worst", and should not read fourteen rows
    // to find out.
    const rows = deriveWhoReported([
      submission({
        id: 1,
        corporation: 'arima_borough_corporation',
        alert_level: 'green',
      }),
      submission({
        id: 2,
        corporation: 'siparia_regional_corporation',
        alert_level: 'red',
      }),
      submission({
        id: 3,
        corporation: 'chaguanas_borough_corporation',
        alert_level: 'yellow',
      }),
    ])

    expect(rows.slice(0, 3).map((row) => row.latest?.alert_level)).toEqual([
      'red',
      'yellow',
      'green',
    ])
  })

  it('keeps a stood-down corporation above one that was never affected', () => {
    const rows = deriveWhoReported([
      submission({
        id: 1,
        corporation: 'arima_borough_corporation',
        alert_level: 'green',
      }),
      submission({
        id: 2,
        corporation: 'siparia_regional_corporation',
        alert_level: 'discontinued',
      }),
    ])

    expect(rows[0].corporation).toBe('siparia_regional_corporation')
  })

  it('keeps corporations that filed above every unreported one, whatever the level', () => {
    // A green filing still outranks silence: "nothing to report" is an answer,
    // and a blank row is a gap to chase.
    const rows = deriveWhoReported([
      submission({
        id: 1,
        corporation: 'arima_borough_corporation',
        alert_level: 'green',
      }),
    ])

    expect(rows[0].corporation).toBe('arima_borough_corporation')
    expect(rows.slice(1).every((row) => row.latest === null)).toBe(true)
  })
})
