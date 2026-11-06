// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FilingsByEvent } from '@/components/dmu/filings-by-event'
import type { EventSummary, SubmissionSummary } from '@/types/dmcu'

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  Link: ({ children }: { children: React.ReactNode }) => <a href="/x">{children}</a>,
}))

afterEach(cleanup)

const EVENT: EventSummary = {
  id: 1,
  corporation: 'arima_borough_corporation',
  title: 'June rains',
  hazard_type: 'adverse_weather',
  started_at: '2026-06-01T00:00:00',
  ended_at: null,
}

const FILING: SubmissionSummary = {
  id: 7,
  corporation: 'arima_borough_corporation',
  event_id: 1,
  event_title: 'June rains',
  as_at: '2026-11-04T18:25:00',
  alert_level: 'yellow',
  sequence_no: 2,
  incident_count: 9,
  log_count: 4,
  report_id: 'r-1',
}

describe('FilingsByEvent', () => {
  it('shows a gap to chase when nothing was filed', () => {
    render(<FilingsByEvent corporation="arima_borough_corporation" filings={[]} events={[]} />)

    expect(
      screen.getByText(
        "This corporation has filed nothing yet. That's a gap to chase, not a report of no incidents.",
      ),
    ).toBeTruthy()
  })

  it('shows each filing under its event', () => {
    render(
      <FilingsByEvent
        corporation="arima_borough_corporation"
        filings={[FILING]}
        events={[EVENT]}
      />,
    )

    expect(screen.getByText('June rains')).toBeTruthy()
    expect(screen.getByText(/Running/)).toBeTruthy()
    expect(screen.getByText('#2')).toBeTruthy()
    expect(screen.getByText('4 Nov 2026, 18:25')).toBeTruthy()
    expect(screen.getByText('Report')).toBeTruthy()
  })

  it('labels filings with no event', () => {
    render(
      <FilingsByEvent
        corporation="arima_borough_corporation"
        filings={[{ ...FILING, event_id: null }]}
        events={[]}
      />,
    )

    expect(screen.getByText('No event')).toBeTruthy()
  })
})
