// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SitrepDraftPane } from './sitrep-draft-pane'
import type { CaptureSession, CaptureSitrep } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

function session(overrides: Partial<CaptureSession> = {}): CaptureSession {
  return {
    id: 4,
    corporation: 'arima_borough_corporation',
    event_id: 2,
    status: 'draft',
    as_at: '2026-08-21T12:00:00',
    alert_level: 'yellow',
    present_activity: 'Shelter open at the community centre.',
    situation_overview: 'River overtopped overnight.',
    incidents: [
      {
        row_id: '1',
        community: 'Arima',
        street: 'Queen Street',
        incident_type: 'flooding',
        raw_incident_type: null,
        incident_summary: 'Five houses flooded',
        event_date: '2026-08-21',
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
      },
    ],
    logs: [
      {
        row_id: '1',
        category: 'activity',
        statement: 'Sandbagging ongoing on Queen Street',
        item: null,
        quantity: null,
        unit: null,
        status: 'ongoing',
      },
    ],
    manual_fields: [],
    messages: [],
    missing: [],
    submission_id: null,
    report_id: null,
    sitrep: null,
    created_at: '2026-08-21T11:00:00',
    updated_at: '2026-08-21T12:00:00',
    ...overrides,
  }
}

function sitrep(overrides: Partial<CaptureSitrep> = {}): CaptureSitrep {
  return {
    markdown:
      '# Corporation Situation Report\n\n**Event:** Flooding in Arima\n\n1 incident [C001].',
    fact_table: { facts: [] },
    violations: [],
    status: 'ok',
    generated_at: '2026-08-21T12:00:00',
    source_updated_at: '2026-08-21T12:00:00',
    stale: false,
    ...overrides,
  }
}

const paneProps = {
  onPreview: vi.fn(),
  onIssue: vi.fn(),
  previewPending: false,
  issuePending: false,
}

describe('SitrepDraftPane', () => {
  it('shows a generate prompt when there is no sitrep yet', () => {
    render(
      <SitrepDraftPane
        session={session()}
        onPreview={vi.fn()}
        onIssue={vi.fn()}
        previewPending={false}
        issuePending={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Generate draft' })).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Issue' })).toBeNull()
  })

  it('renders live markdown and issue when a draft sitrep is present', () => {
    const onIssue = vi.fn()
    render(
      <SitrepDraftPane
        session={session({ sitrep: sitrep() })}
        onPreview={vi.fn()}
        onIssue={onIssue}
        previewPending={false}
        issuePending={false}
      />,
    )
    expect(screen.getByText(/Flooding in Arima/)).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Issue' }))
    expect(onIssue).toHaveBeenCalledTimes(1)
  })

  it('disables issue when the session is already filed', () => {
    render(
      <SitrepDraftPane
        session={session({
          status: 'filed',
          sitrep: sitrep({ markdown: 'Issued body' }),
        })}
        onPreview={vi.fn()}
        onIssue={vi.fn()}
        previewPending={false}
        issuePending={false}
      />,
    )
    expect(
      (screen.getByRole('button', { name: 'Issued' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('calls onPreview from the empty-state generate button', () => {
    const onPreview = vi.fn()
    render(
      <SitrepDraftPane
        session={session()}
        onPreview={onPreview}
        onIssue={vi.fn()}
        previewPending={false}
        issuePending={false}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Generate draft' }))
    expect(onPreview).toHaveBeenCalledTimes(1)
  })

  it('prompts to refresh when the draft sitrep is stale', () => {
    const onPreview = vi.fn()
    render(
      <SitrepDraftPane
        session={session({ sitrep: sitrep({ stale: true }) })}
        onPreview={onPreview}
        onIssue={vi.fn()}
        previewPending={false}
        issuePending={false}
      />,
    )
    expect(
      screen.getByText('Facts changed — refresh to update the draft.'),
    ).not.toBeNull()
    const refresh = screen.getByRole('button', {
      name: 'Refresh',
    }) as HTMLButtonElement
    expect(refresh.disabled).toBe(false)
    fireEvent.click(refresh)
    expect(onPreview).toHaveBeenCalledTimes(1)
  })

  it('hides refresh when the session is filed', () => {
    render(
      <SitrepDraftPane
        session={session({
          status: 'filed',
          sitrep: sitrep({ markdown: 'Issued body' }),
        })}
        {...paneProps}
      />,
    )
    expect(screen.getByRole('button', { name: 'Issued' })).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull()
  })

  it('disables issue while a preview is pending', () => {
    render(
      <SitrepDraftPane
        session={session({ sitrep: sitrep() })}
        onPreview={vi.fn()}
        onIssue={vi.fn()}
        previewPending
        issuePending={false}
      />,
    )
    expect(
      (screen.getByRole('button', { name: 'Issue' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })
})
