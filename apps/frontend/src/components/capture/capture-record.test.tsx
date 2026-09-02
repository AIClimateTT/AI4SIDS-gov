// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
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
  report_id: null,
  sitrep: null,
  created_at: '2026-08-18T14:00:00',
  updated_at: '2026-08-18T14:00:00',
}

describe('CaptureRecord', () => {
  it('saves an incident edit immediately with its manual path recorded', async () => {
    const onSave = vi.fn()
    renderRecord(
      <CaptureRecord session={session} onSave={onSave} onReview={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          manual_fields: ['incident:1.injuries_count'],
        }),
      ),
    )
  })

  it('offers review without repeating the incident count in the footer', () => {
    const onReview = vi.fn()
    renderRecord(
      <CaptureRecord session={session} onSave={vi.fn()} onReview={onReview} />,
    )
    expect(screen.queryByText(/details needed/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /review & file/i }))
    expect(onReview).toHaveBeenCalled()
  })

  it('shows empty placeholders for overview and present activity', () => {
    renderRecord(<CaptureRecord session={session} onSave={vi.fn()} />)
    expect(
      (screen.getByLabelText('Situation overview') as HTMLTextAreaElement)
        .placeholder,
    ).toMatch(/Add a situation overview/)
    expect(
      (screen.getByLabelText('Present activity') as HTMLTextAreaElement)
        .placeholder,
    ).toMatch(/What is happening now/)
  })

  it('saves overview on blur and pins the manual path', () => {
    const onSave = vi.fn()
    renderRecord(<CaptureRecord session={session} onSave={onSave} />)
    const field = screen.getByLabelText('Situation overview')
    fireEvent.change(field, {
      target: { value: 'River overtopped overnight.' },
    })
    fireEvent.blur(field)
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        situation_overview: 'River overtopped overnight.',
        manual_fields: ['situation_overview'],
      }),
    )
  })

  it('saves present activity on blur and pins the manual path', () => {
    const onSave = vi.fn()
    renderRecord(<CaptureRecord session={session} onSave={onSave} />)
    const field = screen.getByLabelText('Present activity')
    fireEvent.change(field, {
      target: { value: 'Shelter open at the centre.' },
    })
    fireEvent.blur(field)
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        present_activity: 'Shelter open at the centre.',
        manual_fields: ['present_activity'],
      }),
    )
  })

  it('shows a tally strip with known injuries', () => {
    renderRecord(<CaptureRecord session={session} onSave={vi.fn()} />)
    expect(screen.getByText(/1 incident · 1 injured/)).not.toBeNull()
  })

  it('does not let a filed session edit situation prose', () => {
    renderRecord(<CaptureRecord session={session} onSave={vi.fn()} disabled />)
    expect(
      (screen.getByLabelText('Situation overview') as HTMLTextAreaElement)
        .disabled,
    ).toBe(true)
    expect(
      (screen.getByLabelText('Present activity') as HTMLTextAreaElement)
        .disabled,
    ).toBe(true)
  })

  it('does not render a separate still-needed list', () => {
    renderRecord(
      <CaptureRecord
        session={{
          ...session,
          missing: [
            {
              path: 'incidents[0].event_date',
              message: 'Date of the incident',
            },
          ],
        }}
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    )
    expect(screen.queryByText('Still needed')).toBeNull()
    expect(
      screen.getByRole('button', { name: 'Date of the incident' }),
    ).not.toBeNull()
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
    expect(payload.logs.map((log: { row_id: string }) => log.row_id)).toEqual([
      '7',
    ])
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
          missing: [
            {
              path: 'incidents[1].event_date',
              message: 'Date of the incident',
            },
          ],
        }}
        onSave={vi.fn()}
        onReview={vi.fn()}
      />,
    )

    // Only the second incident's card should offer the missing-field chip.
    expect(
      screen.getAllByRole('button', { name: 'Date of the incident' }).length,
    ).toBe(1)
  })
})

describe('CaptureRecord situation fields under a live chat turn', () => {
  it('does not overwrite the officer mid-sentence when a chat turn extracts an overview', () => {
    // The edit loss this reproduces: every chat turn saves and refetches the
    // session, so the `value` prop changes under a field the officer may have
    // their cursor in. Adopting it unconditionally erased their typing.
    const { rerender } = renderRecord(
      <CaptureRecord session={session} onSave={vi.fn()} onReview={vi.fn()} />,
    )

    const field = screen.getByLabelText('Situation overview')
    fireEvent.focus(field)
    fireEvent.change(field, { target: { value: 'Riverbank overtopped at' } })

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CaptureRecord
          session={{
            ...session,
            situation_overview: 'Extracted by the assistant',
          }}
          onSave={vi.fn()}
          onReview={vi.fn()}
        />
      </QueryClientProvider>,
    )

    expect((field as HTMLTextAreaElement).value).toBe('Riverbank overtopped at')
  })

  it('still adopts an extracted overview into a field nobody is holding', () => {
    // The other half of the contract: chat extraction has to keep landing, or
    // the officer never sees what the assistant pulled out of their message.
    const { rerender } = renderRecord(
      <CaptureRecord session={session} onSave={vi.fn()} onReview={vi.fn()} />,
    )

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CaptureRecord
          session={{
            ...session,
            situation_overview: 'Extracted by the assistant',
          }}
          onSave={vi.fn()}
          onReview={vi.fn()}
        />
      </QueryClientProvider>,
    )

    expect(
      (screen.getByLabelText('Situation overview') as HTMLTextAreaElement)
        .value,
    ).toBe('Extracted by the assistant')
  })

  it('follows the server again once the officer leaves the field', () => {
    const { rerender } = renderRecord(
      <CaptureRecord session={session} onSave={vi.fn()} onReview={vi.fn()} />,
    )

    const field = screen.getByLabelText('Present activity')
    fireEvent.focus(field)
    fireEvent.change(field, { target: { value: 'Crews deploying' } })
    fireEvent.blur(field)

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CaptureRecord
          session={{
            ...session,
            present_activity: 'Crews deployed to Petit Valley',
          }}
          onSave={vi.fn()}
          onReview={vi.fn()}
        />
      </QueryClientProvider>,
    )

    expect((field as HTMLTextAreaElement).value).toBe(
      'Crews deployed to Petit Valley',
    )
  })

  it('commits on blur only when the text actually changed', () => {
    const onSave = vi.fn()
    renderRecord(
      <CaptureRecord
        session={{ ...session, situation_overview: 'Unchanged' }}
        onSave={onSave}
        onReview={vi.fn()}
      />,
    )

    const field = screen.getByLabelText('Situation overview')
    fireEvent.focus(field)
    fireEvent.blur(field)
    expect(onSave).not.toHaveBeenCalled()
  })
})
