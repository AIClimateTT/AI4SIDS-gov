import { describe, expect, it } from 'vitest'

import { proposeEventFromSession } from '@/lib/propose-event'
import type { CaptureIncident, CaptureSession } from '@/types/dmcu'

function session(overrides: Partial<CaptureSession> = {}): CaptureSession {
  return {
    id: 1,
    corporation: 'arima_borough_corporation',
    event_id: null,
    status: 'draft',
    as_at: '2026-08-21T20:03:00',
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
    created_at: '2026-08-21T20:03:00',
    updated_at: '2026-08-21T20:03:00',
    ...overrides,
  }
}

function incident(overrides: Partial<CaptureIncident> = {}): CaptureIncident {
  return {
    row_id: '1',
    community: null,
    street: null,
    incident_type: null,
    raw_incident_type: null,
    incident_summary: null,
    event_date: null,
    injuries_occurred: null,
    injuries_count: null,
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

describe('proposeEventFromSession', () => {
  it('uses the first sentence of the situation overview as the title', () => {
    const proposal = proposeEventFromSession(
      session({
        situation_overview:
          'The MET Office issued a yellow level warning for flooding on Tumpuna Road. More rain overnight.',
      }),
    )
    expect(proposal.title).toBe(
      'The MET Office issued a yellow level warning for flooding on Tumpuna Road',
    )
  })

  it('falls back to the first incident summary, then place', () => {
    expect(
      proposeEventFromSession(
        session({
          incidents: [
            incident({
              incident_summary: 'Flooding on streets of Tumpuna Road',
              street: 'Tumpuna Road',
              community: 'Arima',
            }),
          ],
        }),
      ).title,
    ).toBe('Flooding on streets of Tumpuna Road')

    expect(
      proposeEventFromSession(
        session({
          incidents: [incident({ street: 'Tumpuna Road', community: 'Arima' })],
        }),
      ).title,
    ).toBe('Tumpuna Road, Arima')
  })

  it('maps incident types to hazard types and dates the event from the incident', () => {
    const proposal = proposeEventFromSession(
      session({
        as_at: '2026-08-22T09:00:00',
        incidents: [
          incident({
            incident_type: 'flooding_',
            incident_summary: 'Flooding on Tumpuna Road',
            event_date: '2026-08-21',
          }),
        ],
      }),
    )
    expect(proposal.hazard_type).toBe('flood')
    expect(proposal.started_at).toBe('2026-08-21')
  })

  it('uses as-at when no incident date is recorded', () => {
    expect(proposeEventFromSession(session()).started_at).toBe('2026-08-21')
    expect(proposeEventFromSession(session()).hazard_type).toBe('other')
    expect(proposeEventFromSession(session({ alert_level: 'none' })).title).toBe(
      'Untitled event',
    )
  })
})
