// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ReviewFileSheet,
  detectDuplicateIncidents,
} from '@/components/capture/review-file-sheet'
import type { CaptureIncident, CaptureSession } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const incident: CaptureIncident = {
  row_id: '1',
  community: 'Petit Valley',
  street: null,
  incident_type: 'flooding',
  raw_incident_type: null,
  incident_summary: '5 houses flooded',
  event_date: '2026-08-18',
  injuries_occurred: false,
  injuries_count: 0,
  deaths_occurred: false,
  deaths_count: 0,
  building_damage: null,
  special_needs_occupants: null,
  estimated_damage_cost: null,
  action_taken: null,
  relief_supplied: null,
  forwarded_to_agency: null,
  further_assessment_required: null,
  other_follow_up: null,
}

const session: CaptureSession = {
  id: 1,
  corporation: 'diego_martin_regional_corporati',
  event_id: 9,
  status: 'draft',
  as_at: '2026-08-18T14:00:00',
  alert_level: 'none',
  present_activity: null,
  situation_overview: null,
  incidents: [incident],
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

describe('ReviewFileSheet', () => {
  it('lists exactly what will be created and blocks filing on a missing event', () => {
    render(
      <ReviewFileSheet
        open
        onOpenChange={vi.fn()}
        session={{ ...session, event_id: null }}
        filing={false}
        onFile={vi.fn()}
      />,
    )
    expect(screen.getByText(/1 incident/)).not.toBeNull()
    expect(screen.getByText(/incidents must be attached to an event/i)).not.toBeNull()
    const button = screen.getByRole('button', { name: /file/i }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })

  it('does not name a report number before the backend assigns one', () => {
    render(
      <ReviewFileSheet open onOpenChange={vi.fn()} session={session} filing={false} onFile={vi.fn()} />,
    )
    const button = screen.getByRole('button', {
      name: 'File situation report',
    }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
    expect(screen.queryByText(/#\d/)).toBeNull()
  })

  it('allows filing with unfilled gaps, showing them as a warning only', () => {
    render(
      <ReviewFileSheet
        open
        onOpenChange={vi.fn()}
        session={{
          ...session,
          missing: [{ path: 'incidents[0].event_date', message: 'Date of the incident' }],
        }}
        filing={false}
        onFile={vi.fn()}
      />,
    )
    expect(screen.getByText(/Date of the incident/)).not.toBeNull()
    const button = screen.getByRole('button', { name: 'File situation report' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
  })

  it('flags incidents that share an incident_summary as possible duplicates', () => {
    const duplicate: CaptureIncident = { ...incident, row_id: '2' }
    render(
      <ReviewFileSheet
        open
        onOpenChange={vi.fn()}
        session={{ ...session, incidents: [incident, duplicate] }}
        filing={false}
        onFile={vi.fn()}
      />,
    )
    expect(screen.getByText(/2 incidents look like duplicates/)).not.toBeNull()
    expect(screen.getAllByText('Possible duplicate').length).toBe(2)
  })
})

describe('detectDuplicateIncidents', () => {
  it('flags rows sharing an incident_summary', () => {
    const duplicate: CaptureIncident = { ...incident, row_id: '2', community: 'Diego Martin' }
    const result = detectDuplicateIncidents([incident, duplicate])
    expect(result.has('1')).toBe(true)
    expect(result.has('2')).toBe(true)
  })

  it('flags rows sharing community + type + date even with different summaries', () => {
    const duplicate: CaptureIncident = {
      ...incident,
      row_id: '2',
      incident_summary: 'Different wording of the same event',
    }
    const result = detectDuplicateIncidents([incident, duplicate])
    expect(result.has('1')).toBe(true)
    expect(result.has('2')).toBe(true)
  })

  it('does not flag genuinely distinct incidents', () => {
    const other: CaptureIncident = {
      ...incident,
      row_id: '2',
      community: 'Diego Martin',
      incident_summary: 'A landslide blocked the main road',
      incident_type: 'landslide',
      event_date: '2026-08-19',
    }
    const result = detectDuplicateIncidents([incident, other])
    expect(result.size).toBe(0)
  })
})
