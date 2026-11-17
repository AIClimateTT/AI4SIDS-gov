// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FilingsByEvent } from '@/components/dmu/filings-by-event'
import type { AdminCaptureSession } from '@/lib/api/admin-capture'
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

  describe('admin capture register', () => {
    const session = (overrides: Partial<AdminCaptureSession>): AdminCaptureSession => ({
      id: 30,
      corporation: 'arima_borough_corporation',
      event_id: 1,
      status: 'draft',
      as_at: '2026-11-16T10:00:00',
      message_count: 5,
      officer_message_count: 2,
      submission_id: null,
      report_id: null,
      has_sitrep: false,
      created_at: '2026-11-16T10:00:00',
      updated_at: '2026-11-16T10:20:00',
      ...overrides,
    })

    it('hides drafts behind a button and shows only that they exist', () => {
      render(
        <FilingsByEvent
          corporation="arima_borough_corporation"
          filings={[FILING]}
          events={[EVENT]}
          captureSessions={[session({})]}
        />,
      )

      expect(screen.queryByText('Draft')).toBeNull()
      fireEvent.click(screen.getByRole('button', { name: /See drafts \(1\)/ }))

      expect(screen.getByText('Draft')).toBeTruthy()
      expect(screen.getByText('Not generated')).toBeTruthy()
      expect(screen.getByRole('button', { name: /Hide drafts/ })).toBeTruthy()
    })

    it('offers a transcript on filed rows that came from a conversation', () => {
      render(
        <FilingsByEvent
          corporation="arima_borough_corporation"
          filings={[FILING]}
          events={[EVENT]}
          captureSessions={[session({ id: 31, status: 'filed', submission_id: 7 })]}
        />,
      )

      expect(screen.getByRole('button', { name: /Transcript/ })).toBeTruthy()
      expect(screen.queryByRole('button', { name: /See drafts/ })).toBeNull()
    })

    it('shows no drafts or transcripts without the admin register', () => {
      render(
        <FilingsByEvent
          corporation="arima_borough_corporation"
          filings={[FILING]}
          events={[EVENT]}
        />,
      )

      expect(screen.queryByRole('button', { name: /Transcript/ })).toBeNull()
      expect(screen.queryByRole('button', { name: /See drafts/ })).toBeNull()
    })

    it('puts drafts with no event under a No event group', () => {
      render(
        <FilingsByEvent
          corporation="arima_borough_corporation"
          filings={[]}
          events={[]}
          captureSessions={[session({ event_id: null })]}
        />,
      )

      expect(screen.getByText('No event')).toBeTruthy()
      expect(screen.getByRole('button', { name: /See drafts \(1\)/ })).toBeTruthy()
    })
  })
})
