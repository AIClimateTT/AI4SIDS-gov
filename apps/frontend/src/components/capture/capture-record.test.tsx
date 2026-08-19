// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CaptureRecord } from '@/components/capture/capture-record'
import type { CaptureSession } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

// CaptureRecord mounts a real EventChip, which calls the real
// useAttachCaptureEvent mutation hook -- that needs a QueryClient in
// context even though none of these tests exercise attaching.
function renderRecord(ui: ReactElement) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  )
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
  incidents: [
    {
      row_id: '1',
      community: 'Petit Valley',
      street: null,
      incident_type: 'flooding',
      incident_summary: '5 houses flooded',
      event_date: null,
      // Nonzero and already "occurred" so that editing the count alone
      // (below) does not also flip the derived injuries_occurred flag --
      // IncidentCard reports that flag as a second path whenever it
      // actually changes, so pinning it here keeps this test's expected
      // manual_fields to exactly the one path under test.
      injuries_occurred: true,
      injuries_count: 1,
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

describe('CaptureRecord', () => {
  it('saves an incident edit immediately with its manual path recorded', async () => {
    const onSave = vi.fn()
    renderRecord(<CaptureRecord session={session} onSave={onSave} onReview={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ manual_fields: ['incident:1.injuries_count'] }),
      ),
    )
  })

  it('summarises the record and offers review', () => {
    const onReview = vi.fn()
    renderRecord(<CaptureRecord session={session} onSave={vi.fn()} onReview={onReview} />)
    expect(screen.getByText(/1 incident/)).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /review & file/i }))
    expect(onReview).toHaveBeenCalled()
  })

  it('does not render a separate still-needed list', () => {
    renderRecord(
      <CaptureRecord
        session={{
          ...session,
          missing: [{ path: 'incidents[0].event_date', message: 'Date of the incident' }],
        }}
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    )
    expect(screen.queryByText('Still needed')).toBeNull()
    expect(screen.getByRole('button', { name: 'Date of the incident' })).not.toBeNull()
  })

  it('removes a situation log by row_id, not by its position in the list', () => {
    const onSave = vi.fn()
    renderRecord(
      <CaptureRecord
        session={{
          ...session,
          logs: [
            {
              row_id: '5',
              category: 'resource',
              statement: 'Generators available',
              item: null,
              quantity: null,
              unit: null,
              status: null,
            },
            {
              row_id: '7',
              category: 'resource',
              statement: 'Water trucks deployed',
              item: null,
              quantity: null,
              unit: null,
              status: null,
            },
          ],
        }}
        onSave={onSave}
        onReview={vi.fn()}
      />,
    )

    // The one incident's own Remove button renders first; the two logs'
    // Remove buttons follow in the order the logs appear.
    const removeButtons = screen.getAllByRole('button', { name: 'Remove' })
    fireEvent.click(removeButtons[1])

    const payload = onSave.mock.calls[0][0]
    expect(payload.logs.map((log: { row_id: string }) => log.row_id)).toEqual(['7'])
  })

  it('filters missing-field chips to the incident at the matching array index', () => {
    renderRecord(
      <CaptureRecord
        session={{
          ...session,
          incidents: [
            session.incidents[0],
            {
              ...session.incidents[0],
              row_id: '2',
              incident_summary: 'Second incident',
            },
          ],
          missing: [{ path: 'incidents[1].event_date', message: 'Date of the incident' }],
        }}
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    )

    // Only the second incident's card should offer the missing-field chip.
    expect(screen.getAllByRole('button', { name: 'Date of the incident' }).length).toBe(1)
  })
})
