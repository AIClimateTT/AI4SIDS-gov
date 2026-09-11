// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  FILE_TO_STORE_WARNING,
  ReviewBriefingSheet,
} from '@/components/whatsapp/review-briefing-sheet'
import type { WhatsAppDraft } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const CORP = 'diego_martin_regional_corporati'

function draft(overrides: Partial<WhatsAppDraft> = {}): WhatsAppDraft {
  return {
    id: 1,
    draft_id: 1,
    filename: 'hour.txt',
    source_kind: 'export',
    as_at: '2026-08-15T16:00:00',
    message_count: 2,
    pii_redacted: false,
    incidents: [
      {
        row_id: '1',
        corporation: CORP,
        community: 'Petit Valley',
        street: null,
        incident_type: 'flooding_',
        incident_summary: '3 houses flooded',
        event_date: '2026-08-15',
        injuries_count: null,
        deaths_count: null,
        source_index: 1,
        source_quote: '3 houses flooded in Petit Valley',
        included: true,
      },
      {
        row_id: '2',
        corporation: null,
        community: 'Unknown',
        street: null,
        incident_type: null,
        incident_summary: 'Water on the road',
        event_date: null,
        injuries_count: null,
        deaths_count: null,
        source_index: 2,
        source_quote: 'Water on the road',
        included: false,
      },
    ],
    logs: [
      {
        row_id: '1',
        corporation: CORP,
        category: 'resource',
        statement: '200 sandbags remaining at depot',
        item: 'sandbags',
        quantity: 200,
        unit: 'bags',
        status: 'available',
        source_index: 3,
        source_quote: '200 sandbags remaining at depot',
        included: true,
      },
    ],
    messages: [],
    manual_fields: [],
    missing: [],
    status: 'ready',
    error: null,
    briefing_report_id: null,
    briefing_stale: false,
    created_at: '2026-08-15T16:00:00',
    updated_at: '2026-08-15T16:00:00',
    ...overrides,
  }
}

describe('ReviewBriefingSheet', () => {
  it('lists included attributed rows and warns on missing corporations', () => {
    render(
      <ReviewBriefingSheet
        draft={draft()}
        open
        onOpenChange={vi.fn()}
        briefingPending={false}
        promotePending={false}
        onBrief={vi.fn()}
        onPromote={vi.fn()}
      />,
    )

    expect(screen.getByText('3 houses flooded')).not.toBeNull()
    expect(screen.getByText('200 sandbags remaining at depot')).not.toBeNull()
    expect(screen.queryByText('Water on the road')).toBeNull()
    expect(
      screen.getByText(
        '1 row has no corporation and will not appear in the briefing.',
      ),
    ).not.toBeNull()
    expect(screen.getByText(FILE_TO_STORE_WARNING)).not.toBeNull()
  })

  it('disables File and Brief when nothing is included and attributed', () => {
    const empty: WhatsAppDraft = draft({
      incidents: [
        {
          ...draft().incidents[0],
          included: false,
        },
      ],
      logs: [],
    })
    render(
      <ReviewBriefingSheet
        draft={empty}
        open
        onOpenChange={vi.fn()}
        briefingPending={false}
        promotePending={false}
        onBrief={vi.fn()}
        onPromote={vi.fn()}
      />,
    )

    expect(
      (screen.getByRole('button', { name: 'File to store' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(
      (
        screen.getByRole('button', {
          name: 'Generate briefing',
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true)
  })

  it('generates from the sheet and closes', () => {
    const onBrief = vi.fn()
    const onOpenChange = vi.fn()
    render(
      <ReviewBriefingSheet
        draft={draft()}
        open
        onOpenChange={onOpenChange}
        briefingPending={false}
        promotePending={false}
        onBrief={onBrief}
        onPromote={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Generate briefing' }))
    expect(onBrief).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
