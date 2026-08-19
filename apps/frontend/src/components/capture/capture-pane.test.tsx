// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CapturePane } from '@/components/capture/capture-pane'
import type { CaptureSession } from '@/types/dmcu'

const session: CaptureSession = {
  id: 1,
  corporation: 'diego_martin_regional_corporati',
  event_id: 9,
  status: 'draft',
  as_at: '2026-08-18T14:00:00',
  alert_level: 'none',
  present_activity: null,
  situation_overview: null,
  incidents: [
    {
      row_id: '1',
      community: 'Petit Valley',
      street: null,
      incident_type: 'flooding',
      incident_summary: '5 houses flooded',
      event_date: null,
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
      raw_incident_type: null,
    },
  ],
  logs: [],
  messages: [],
  missing: [],
  submission_id: null,
  created_at: '2026-08-18T14:00:00',
  updated_at: '2026-08-18T14:00:00',
}

describe('CapturePane add forms', () => {
  it('keeps incident and log lists visible and hides add forms until Add is clicked', () => {
    render(<CapturePane session={session} onSave={vi.fn()} />)

    expect(screen.getByText('5 houses flooded')).not.toBeNull()
    expect(screen.getByText('No situation logs captured yet.')).not.toBeNull()
    expect(screen.queryByLabelText('Summary')).toBeNull()
    expect(screen.queryByLabelText('Statement')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Add incident' }))
    expect(screen.getByText('Summary')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Add log' }))
    expect(screen.getByText('Statement')).not.toBeNull()
  })

  it('keeps in-progress typing when the session updates from a chat turn', () => {
    const { rerender } = render(
      <CapturePane session={session} onSave={vi.fn()} />,
    )
    const overview = screen.getByLabelText('Situation overview')
    fireEvent.change(overview, { target: { value: 'Water rising on Diego Martin Main Rd' } })

    // An LLM turn lands: same session id, new updated_at, model-written fields.
    rerender(
      <CapturePane
        session={{
          ...session,
          updated_at: '2026-08-18T14:05:00',
          present_activity: 'Heavy rainfall',
        }}
        onSave={vi.fn()}
      />,
    )

    const after = screen.getByLabelText('Situation overview') as HTMLTextAreaElement
    expect(after.value).toBe('Water rising on Diego Martin Main Rd')
  })
})
