// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WhoHasReported, reportingHeadline } from '@/components/dmu/who-has-reported'
import { deriveWhoReported } from '@/lib/who-reported'
import type { SubmissionSummary } from '@/types/dmcu'

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  Link: ({ children }: { children: React.ReactNode }) => <a href="/x">{children}</a>,
}))

afterEach(cleanup)

const NOW = new Date('2026-11-06T12:00:00')

const FILING: SubmissionSummary = {
  id: 1,
  corporation: 'arima_borough_corporation',
  event_id: null,
  event_title: null,
  as_at: new Date(NOW.getTime() - 50 * 3_600_000).toISOString(),
  alert_level: 'yellow',
  sequence_no: 1,
  incident_count: 9,
  log_count: 4,
}

function renderPanel(onWindowChange = vi.fn()) {
  const { rows, reportedCount } = deriveWhoReported([FILING], NOW, 24)
  render(
    <WhoHasReported
      rows={rows}
      reportedCount={reportedCount}
      windowHours={24}
      onWindowChange={onWindowChange}
      now={NOW}
    />,
  )
  return onWindowChange
}

describe('WhoHasReported', () => {
  it('states the count in words', () => {
    expect(reportingHeadline(1, 14, 24)).toBe('1 of 14 in the last 24 hours')
  })

  it('shows how long since an out-of-window corporation filed', () => {
    renderPanel()

    expect(screen.getByText('Last filed 2 days ago')).toBeTruthy()
  })

  it('dates a filing from long ago', () => {
    const old = { ...FILING, as_at: '2023-06-30T16:00:00' }
    const { rows, reportedCount } = deriveWhoReported([old], NOW, 24)
    render(
      <WhoHasReported
        rows={rows}
        reportedCount={reportedCount}
        windowHours={24}
        onWindowChange={vi.fn()}
        now={NOW}
      />,
    )

    expect(screen.getByText('Last filed on 30 Jun 2023')).toBeTruthy()
  })

  it('says never filed, not zero', () => {
    renderPanel()

    expect(screen.getAllByText('Never filed')).toHaveLength(13)
  })

  it('asks to change the window', () => {
    const onWindowChange = renderPanel()

    fireEvent.click(screen.getByRole('button', { name: '7 days' }))

    expect(onWindowChange).toHaveBeenCalledWith(168)
  })
})
