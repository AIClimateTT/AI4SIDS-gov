// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AttachEventBody, CaptureSession, EventSummary } from '@/types/dmcu'

type AttachInput = { id: number; body: AttachEventBody }
type AttachFn = (input: AttachInput) => void

const mockState = vi.hoisted(() => ({ mutate: (() => {}) as AttachFn }))

vi.mock('@/lib/queries/capture', () => ({
  useAttachCaptureEvent: () => mockState,
}))

import { EventChip } from '@/components/capture/event-chip'

afterEach(() => {
  cleanup()
})

const sessionWithoutEvent: CaptureSession = {
  id: 1,
  corporation: 'diego_martin_regional_corporati',
  event_id: null,
  status: 'draft',
  as_at: '2026-08-18T14:00:00',
  alert_level: 'none',
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
  created_at: '2026-08-18T14:00:00',
  updated_at: '2026-08-18T14:00:00',
}

const runningEvent: EventSummary = {
  id: 9,
  corporation: 'diego_martin_regional_corporati',
  title: 'August flooding',
  hazard_type: 'flood',
  started_at: '2026-08-15',
  ended_at: null,
}

const otherRunningEvent: EventSummary = {
  ...runningEvent,
  id: 10,
  title: 'Ravine landslide',
}

function renderChip({
  session,
  events,
  attach,
}: {
  session: CaptureSession
  events: EventSummary[]
  attach: AttachFn
}) {
  mockState.mutate = attach
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <EventChip session={session} events={events} />
    </QueryClientProvider>,
  )
}

describe('EventChip', () => {
  it('never attaches an event without an explicit action', () => {
    const attach = vi.fn()
    renderChip({ session: sessionWithoutEvent, events: [runningEvent], attach })
    expect(attach).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /August flooding/ })).not.toBeNull()
  })

  it('attaches the single running event in one click', () => {
    const attach = vi.fn()
    renderChip({ session: sessionWithoutEvent, events: [runningEvent], attach })
    fireEvent.click(screen.getByRole('button', { name: /August flooding/ }))
    expect(attach).toHaveBeenCalledWith({ id: 1, body: { event_id: 9 } })
  })

  it('offers a picker rather than guessing when several events are running', () => {
    renderChip({
      session: sessionWithoutEvent,
      events: [runningEvent, otherRunningEvent],
      attach: vi.fn(),
    })
    expect(screen.getByRole('button', { name: 'No event' })).not.toBeNull()
  })

  it('shows the attached event title and never re-attaches on render alone', () => {
    const attach = vi.fn()
    renderChip({
      session: { ...sessionWithoutEvent, event_id: 9 },
      events: [runningEvent],
      attach,
    })
    expect(attach).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'August flooding' })).not.toBeNull()
  })
})
