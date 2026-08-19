// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CapturePane } from '@/components/capture/capture-pane'
import type { CaptureSession } from '@/types/dmcu'

// This project's vitest config does not set `test.globals`, so
// @testing-library/react's automatic afterEach(cleanup) detection never
// registers. Without an explicit unmount, a form field's DOM node from an
// earlier test in this file stays attached (duplicate ids, since every
// CapturePane instance reuses the same field names), and label-based
// queries can resolve to the wrong instance. Clean up explicitly.
afterEach(() => {
  cleanup()
})

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
  manual_fields: [],
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

  it('adopts server updates again after the officer saves', async () => {
    const onSave = vi.fn()
    const { rerender } = render(<CapturePane session={session} onSave={onSave} />)

    const overview = screen.getByLabelText('Situation overview')
    fireEvent.change(overview, { target: { value: 'Water rising on Diego Martin Main Rd' } })

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())

    // A later chat turn brings a genuinely new server value, after the save.
    rerender(
      <CapturePane
        session={{
          ...session,
          updated_at: '2026-08-18T15:00:00',
          situation_overview: 'Evacuation underway on Diego Martin Main Rd',
        }}
        onSave={onSave}
      />,
    )

    await waitFor(() => {
      const after = screen.getByLabelText('Situation overview') as HTMLTextAreaElement
      expect(after.value).toBe('Evacuation underway on Diego Martin Main Rd')
    })
  })
})
