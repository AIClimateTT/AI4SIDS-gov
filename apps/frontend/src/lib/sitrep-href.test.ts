// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'

import { resolveSitrepHref } from '@/lib/sitrep-href'
import type { CaptureSession } from '@/types/dmcu'

const session = (overrides: Partial<CaptureSession>): CaptureSession => ({
  id: 1,
  corporation: 'arima_borough_corporation',
  event_id: 2,
  status: 'filed',
  as_at: '2026-08-21T12:00:00',
  alert_level: 'yellow',
  present_activity: null,
  situation_overview: null,
  incidents: [],
  logs: [],
  manual_fields: [],
  messages: [],
  missing: [],
  submission_id: null,
  report_id: null,
  sitrep: null,
  created_at: '2026-08-21T11:00:00',
  updated_at: '2026-08-21T12:00:00',
  ...overrides,
})

describe('resolveSitrepHref', () => {
  it('prefers the capture session that filed the submission', () => {
    const href = resolveSitrepHref(
      { id: 88, event_id: 2 },
      [session({ id: 9, submission_id: 88 })],
    )
    expect(href).toEqual({
      to: '/corp/c/$sessionId',
      params: { sessionId: '9' },
    })
  })

  it('falls back to a session on the same event, then the event page', () => {
    expect(
      resolveSitrepHref({ id: 88, event_id: 2 }, [session({ id: 4, event_id: 2 })]),
    ).toEqual({ to: '/corp/c/$sessionId', params: { sessionId: '4' } })

    expect(resolveSitrepHref({ id: 88, event_id: 2 }, [])).toEqual({
      to: '/corp/events/$eventId',
      params: { eventId: '2' },
    })
  })

  it('sends event-less unmatched filings home', () => {
    expect(resolveSitrepHref({ id: 88, event_id: null }, [])).toEqual({
      to: '/corp',
    })
  })
})
