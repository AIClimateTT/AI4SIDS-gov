// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { IncidentCard } from '@/components/capture/incident-card'
import type { CaptureIncident } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const incident = {
  row_id: '1',
  community: 'Petit Valley',
  street: null,
  incident_type: 'flooding',
  raw_incident_type: null,
  incident_summary: '5 houses flooded',
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
} satisfies CaptureIncident

describe('IncidentCard', () => {
  it('reads as prose until it is opened', () => {
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={vi.fn()} onRemove={vi.fn()} />,
    )
    expect(screen.getByText('5 houses flooded')).not.toBeNull()
    expect(screen.queryByLabelText('Community')).toBeNull()
  })

  it('reports only the changed field as a manual path', async () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(onEdit).toHaveBeenCalledWith(
        expect.objectContaining({ injuries_count: 4 }),
        ['incident:1.injuries_count'],
      ),
    )
  })

  it('reports exactly one path when exactly one field is edited', async () => {
    // This is the property the manual-field provenance mechanism depends
    // on: a field the officer opened and left alone must not be reported
    // as changed, and a field they never opened must not appear either.
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(onEdit).toHaveBeenCalled())
    const [, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(paths.length).toBe(1)
    expect(paths[0]).toBe('incident:1.injuries_count')
  })

  it('offers each missing detail as a control that opens the card', () => {
    render(
      <IncidentCard
        incident={incident}
        missing={[{ path: 'incidents[0].event_date', message: 'Date of the incident' }]}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Date of the incident' }))
    expect(screen.getByLabelText('Date')).not.toBeNull()
  })

  it('maps the synthetic casualties path to the injuries_count field', () => {
    render(
      <IncidentCard
        incident={incident}
        missing={[
          { path: 'incidents[0].casualties', message: 'Whether injuries or deaths occurred' },
        ]}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Whether injuries or deaths occurred' }),
    )
    expect(screen.getByLabelText('Injuries count')).not.toBeNull()
  })

  it('does not call onEdit when the officer opens and saves with no changes', async () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    // The card closes (the edit form unmounts) once the submit resolves,
    // which is the deterministic signal that the async save handler ran.
    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull())
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('does not read an empty text input as a change from null', async () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    // Street is null on the incident and starts as an empty input; touching
    // it without changing its effective value must not register as a diff.
    fireEvent.change(screen.getByLabelText('Street'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull())
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('calls onRemove when Remove is clicked', () => {
    const onRemove = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={vi.fn()} onRemove={onRemove} />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(onRemove).toHaveBeenCalled()
  })

  it('hides Edit and Remove controls when disabled', () => {
    render(
      <IncidentCard
        incident={incident}
        missing={[]}
        disabled
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Remove' })).toBeNull()
  })
})
