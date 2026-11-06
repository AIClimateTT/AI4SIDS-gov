import { describe, expect, it } from 'vitest'

import { CANONICAL_CORPORATIONS, CORPORATION_LABELS } from '@/lib/corporations'
import { deriveWhoReported, highestAlert, lastFiledLabel } from '@/lib/who-reported'
import type { SubmissionSummary } from '@/types/dmcu'

const NOW = new Date('2026-11-06T12:00:00')

function hoursAgo(hours: number): string {
  return new Date(NOW.getTime() - hours * 3_600_000).toISOString()
}

function submission(overrides: Partial<SubmissionSummary>): SubmissionSummary {
  return {
    id: 1,
    corporation: 'arima_borough_corporation',
    event_id: null,
    event_title: null,
    as_at: hoursAgo(1),
    alert_level: 'green',
    sequence_no: 1,
    incident_count: 0,
    log_count: 0,
    ...overrides,
  }
}

describe('deriveWhoReported', () => {
  it('gives every corporation a row when nothing was filed', () => {
    const { rows, reportedCount } = deriveWhoReported([], NOW, 24)

    expect(reportedCount).toBe(0)
    expect(rows).toHaveLength(CANONICAL_CORPORATIONS.length)
    expect(rows.every((row) => row.latest === null && !row.inWindow)).toBe(true)
    expect(rows.find((r) => r.corporation === 'arima_borough_corporation')?.label).toBe(
      CORPORATION_LABELS.arima_borough_corporation,
    )
  })

  it('uses the latest filing whatever the order', () => {
    const { rows } = deriveWhoReported(
      [submission({ id: 1, as_at: hoursAgo(5) }), submission({ id: 2, as_at: hoursAgo(1) })],
      NOW,
      24,
    )

    expect(rows.find((r) => r.corporation === 'arima_borough_corporation')?.latest?.id).toBe(2)
  })

  it('treats a 25-hour-old filing as out of a 24-hour window but in a 7-day one', () => {
    const filings = [submission({ as_at: hoursAgo(25) })]

    expect(deriveWhoReported(filings, NOW, 24).reportedCount).toBe(0)
    expect(deriveWhoReported(filings, NOW, 168).reportedCount).toBe(1)
  })

  it('puts corporations to chase first, in corporation order', () => {
    const { rows } = deriveWhoReported([submission({})], NOW, 24)

    expect(rows.at(-1)?.corporation).toBe('arima_borough_corporation')
    const chase = rows.filter((row) => !row.inWindow).map((row) => row.corporation)
    expect(chase).toEqual(
      CANONICAL_CORPORATIONS.filter((c) => c !== 'arima_borough_corporation'),
    )
  })

  it('orders reported corporations most severe first', () => {
    const { rows } = deriveWhoReported(
      [
        submission({ alert_level: 'yellow' }),
        submission({ id: 2, corporation: 'siparia_regional_corporation', alert_level: 'red' }),
      ],
      NOW,
      24,
    )

    expect(rows.filter((r) => r.inWindow).map((r) => r.corporation)).toEqual([
      'siparia_regional_corporation',
      'arima_borough_corporation',
    ])
  })
})

describe('highestAlert', () => {
  it('names the worst level among corporations in the window', () => {
    const { rows } = deriveWhoReported(
      [
        submission({ alert_level: 'yellow' }),
        submission({ id: 2, corporation: 'siparia_regional_corporation', alert_level: 'red' }),
      ],
      NOW,
      24,
    )

    expect(highestAlert(rows)?.corporation).toBe('siparia_regional_corporation')
  })

  it('ignores filings outside the window', () => {
    const { rows } = deriveWhoReported(
      [submission({ alert_level: 'red', as_at: hoursAgo(30) })],
      NOW,
      24,
    )

    expect(highestAlert(rows)).toBeNull()
  })
})

describe('lastFiledLabel', () => {
  it.each([
    [null, 'Never filed'],
    [0.2, 'Just now'],
    [1, '1 hour ago'],
    [3, '3 hours ago'],
    [24, '1 day ago'],
    [50, '2 days ago'],
  ])('%s hours old reads %s', (hours, label) => {
    expect(lastFiledLabel(hours === null ? null : hoursAgo(hours), NOW)).toBe(label)
  })

  it('reads a time ahead of now as just now', () => {
    expect(lastFiledLabel(hoursAgo(-2), NOW)).toBe('Just now')
  })
})
