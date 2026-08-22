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

// Everything optional is null, including incident_type — the exact shape
// an officer sees when they tap the "Incident type" missing-field chip.
const bareIncident = {
  ...incident,
  community: null,
  street: null,
  incident_type: null,
  incident_summary: 'Unassessed report',
  event_date: null,
} satisfies CaptureIncident

describe('IncidentCard', () => {
  it('shows known casualties on the closed card without opening Edit', () => {
    render(
      <IncidentCard
        incident={{
          ...incident,
          injuries_occurred: true,
          injuries_count: 1,
          deaths_occurred: false,
          deaths_count: 0,
        }}
        missing={[]}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    expect(screen.getByText(/1 injured/)).not.toBeNull()
    expect(screen.getByText(/0 dead/)).not.toBeNull()
    expect(screen.queryByLabelText('Community')).toBeNull()
  })

  it('does not claim zero injuries when casualties are unknown', () => {
    render(
      <IncidentCard incident={bareIncident} missing={[]} onEdit={vi.fn()} onRemove={vi.fn()} />,
    )
    expect(screen.queryByText(/0 injured/)).toBeNull()
    expect(screen.getByText('Casualties unknown')).not.toBeNull()
    expect(screen.queryByLabelText('Community')).toBeNull()
  })

  it('reports the derived injuries_occurred flag alongside injuries_count when it changes', async () => {
    // injuries_occurred is not a field the officer types into directly --
    // applyIncidentForm derives it from injuries_count. When that derived
    // value actually changes it must be reported too, or a hand-edited
    // count (pinned) can end up contradicting an unpinned, model-owned
    // "occurred" flag on a later chat turn.
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
    const [next, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(next.injuries_count).toBe(4)
    expect(next.injuries_occurred).toBe(true)
    expect(paths).toEqual(
      expect.arrayContaining(['incident:1.injuries_count', 'incident:1.injuries_occurred']),
    )
    expect(paths.length).toBe(2)
  })

  it('reports the derived deaths_occurred flag alongside deaths_count when it changes', async () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Deaths count'), {
      target: { value: '1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(onEdit).toHaveBeenCalled())
    const [next, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(next.deaths_count).toBe(1)
    expect(next.deaths_occurred).toBe(true)
    expect(paths).toEqual(
      expect.arrayContaining(['incident:1.deaths_count', 'incident:1.deaths_occurred']),
    )
    expect(paths.length).toBe(2)
  })

  it('clearing a previously-set injuries_count back to empty reports both fields, with the flag as null not false', async () => {
    // null is "unknown"; false is "known: none occurred". Clearing the
    // count back to unknown must not assert the stronger claim that no
    // injuries occurred.
    const injuredIncident = {
      ...incident,
      injuries_count: 4,
      injuries_occurred: true,
    } satisfies CaptureIncident
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={injuredIncident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Injuries count'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(onEdit).toHaveBeenCalled())
    const [next, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(next.injuries_count).toBeNull()
    expect(next.injuries_occurred).toBeNull()
    expect(paths).toEqual(
      expect.arrayContaining(['incident:1.injuries_count', 'incident:1.injuries_occurred']),
    )
    expect(paths.length).toBe(2)
  })

  it('reports exactly one path when exactly one field (with no derived counterpart) is edited', async () => {
    // This is the property the manual-field provenance mechanism depends
    // on: a field the officer opened and left alone must not be reported
    // as changed, and a field they never opened must not appear either.
    // Community has no derived counterpart, so it is a clean demonstration
    // of "edit one field, get exactly one path" (unlike injuries/deaths
    // count, which legitimately produce two).
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Community'), {
      target: { value: 'Diego Martin' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(onEdit).toHaveBeenCalled())
    const [, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(paths.length).toBe(1)
    expect(paths[0]).toBe('incident:1.community')
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

  it('does not call onEdit when a null-type incident is opened and saved with no edits', async () => {
    // Regression: seeding the type select with 'other' (a real category)
    // instead of '' (no-selection) made an untouched null field look
    // edited on save, permanently pinning 'other' as a manual value.
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={bareIncident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull())
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('does not call onEdit when a field is typed into and cleared back to empty', async () => {
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={bareIncident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    const community = screen.getByLabelText('Community')
    fireEvent.change(community, { target: { value: 'x' } })
    fireEvent.change(community, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull())
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('leaves incident_type untouched when an unrelated field is the only edit', async () => {
    // Street has no derived counterpart (unlike deaths_count, which
    // legitimately produces a second path via deaths_occurred -- see the
    // dedicated derived-flag tests above), so it cleanly demonstrates that
    // editing one field doesn't disturb incident_type.
    const onEdit = vi.fn()
    render(
      <IncidentCard incident={incident} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Street'), { target: { value: 'Main Road' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(onEdit).toHaveBeenCalled())
    const [next, paths] = onEdit.mock.calls[0] as [CaptureIncident, string[]]
    expect(paths).toStrictEqual(['incident:1.street'])
    expect(next.incident_type).toBe('flooding')
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
