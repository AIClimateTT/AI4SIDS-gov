// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AttachEventBody, CaptureIncident, CaptureSession, EventSummary } from '@/types/dmcu'

type AttachInput = { id: number; body: AttachEventBody }
type AttachFn = (input: AttachInput) => void

const mockState = vi.hoisted(() => ({ mutate: (() => {}) as AttachFn }))

vi.mock('@/lib/queries/capture', () => ({
  useAttachCaptureEvent: () => mockState,
}))

import { EventConfirmBanner } from '@/components/capture/event-confirm-banner'

afterEach(() => {
  cleanup()
})

function incident(overrides: Partial<CaptureIncident> = {}): CaptureIncident {
  return {
    row_id: '1',
    community: 'Arima',
    street: 'Tumpuna Road',
    incident_type: 'flooding_',
    raw_incident_type: null,
    incident_summary: 'Flooding on streets of Tumpuna Road',
    event_date: '2026-08-21',
    injuries_occurred: null,
    injuries_count: 1,
    deaths_occurred: null,
    deaths_count: null,
    building_damage: null,
    special_needs_occupants: null,
    estimated_damage_cost: null,
    action_taken: null,
    relief_supplied: null,
    forwarded_to_agency: null,
    further_assessment_required: null,
    other_follow_up: null,
    ...overrides,
  }
}

const session: CaptureSession = {
  id: 1,
  corporation: 'arima_borough_corporation',
  event_id: null,
  status: 'draft',
  as_at: '2026-08-21T20:03:00',
  alert_level: 'yellow',
  present_activity: null,
  situation_overview:
    'The MET Office issued a yellow level warning for flooding on Tumpuna Road.',
  incidents: [incident()],
  logs: [],
  manual_fields: [],
  messages: [],
  missing: [],
  submission_id: null,
  report_id: null,
  sitrep: null,
  created_at: '2026-08-21T20:03:00',
  updated_at: '2026-08-21T20:03:00',
}

const augustFlooding: EventSummary = {
  id: 9,
  corporation: 'arima_borough_corporation',
  title: 'August flooding',
  hazard_type: 'flood',
  started_at: '2026-08-15',
  ended_at: null,
}

const landslide: EventSummary = {
  ...augustFlooding,
  id: 10,
  title: 'Ravine landslide',
}

function renderBanner(events: EventSummary[], attach: AttachFn = vi.fn()) {
  mockState.mutate = attach
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <EventConfirmBanner session={session} events={events} />
    </QueryClientProvider>,
  )
}

describe('EventConfirmBanner', () => {
  it('does not attach on render', () => {
    const attach = vi.fn()
    renderBanner([], attach)
    expect(attach).not.toHaveBeenCalled()
  })

  it('creates a new event from the working-set proposal when none are running', () => {
    const attach = vi.fn()
    renderBanner([], attach)
    fireEvent.click(screen.getByRole('button', { name: 'Confirm event' }))
    expect(attach).toHaveBeenCalledWith({
      id: 1,
      body: {
        title:
          'The MET Office issued a yellow level warning for flooding on Tumpuna Road',
        hazard_type: 'flood',
        started_at: '2026-08-21',
      },
    })
  })

  it('offers the single running event without creating on render', () => {
    const attach = vi.fn()
    renderBanner([augustFlooding], attach)
    expect(attach).not.toHaveBeenCalled()
    fireEvent.click(
      screen.getByRole('button', { name: 'This is part of August flooding' }),
    )
    expect(attach).toHaveBeenCalledWith({ id: 1, body: { event_id: 9 } })
  })

  it('lists every running event when several are open', () => {
    renderBanner([augustFlooding, landslide])
    expect(
      screen.getByRole('button', { name: 'This is part of August flooding' }),
    ).not.toBeNull()
    expect(
      screen.getByRole('button', { name: 'This is part of Ravine landslide' }),
    ).not.toBeNull()
  })
})
