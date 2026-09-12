// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/shared', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/shared')>()
  return {
    ...actual,
    ButtonLink: ({ children }: { children?: React.ReactNode }) => (
      <a>{children}</a>
    ),
  }
})

import {
  BRIEFING_EMPTY_TITLE,
  BRIEFING_STALE_COPY,
  WhatsAppBriefingPane,
} from '@/components/whatsapp/briefing-pane'
import { FILE_TO_STORE_WARNING } from '@/components/whatsapp/review-briefing-sheet'
import type { ReportDetail, WhatsAppDraft } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const draft: WhatsAppDraft = {
  id: 1,
  draft_id: 1,
  filename: 'hour.txt',
  source_kind: 'export',
  as_at: '2026-08-15T16:00:00',
  message_count: 1,
  pii_redacted: false,
  incidents: [
    {
      row_id: '1',
      corporation: 'diego_martin_regional_corporati',
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
  ],
  logs: [],
  messages: [],
  manual_fields: [],
  missing: [],
  status: 'ready',
  error: null,
  briefing_report_id: null,
  briefing_stale: false,
  created_at: '2026-08-15T16:00:00',
  updated_at: '2026-08-15T16:00:00',
}

const report: ReportDetail = {
  id: 'r1',
  template: 'whatsapp_hour_briefing',
  template_version: 1,
  params: {},
  data_requirements: [],
  fact_table: { facts: [] },
  narrative: '',
  markdown:
    '**Provisional — WhatsApp hour briefing, not a cited national SITREP.**\n\n3 houses flooded.',
  status: 'ok',
  violations: [],
  created_at: '2026-08-15T16:05:00',
}

const paneProps = {
  includedCount: 1,
  briefingPending: false,
  promotePending: false,
  onReview: vi.fn(),
  onPromote: vi.fn(),
}

describe('WhatsAppBriefingPane', () => {
  it('shows the empty-state prompt when there is no briefing yet', () => {
    render(<WhatsAppBriefingPane draft={draft} {...paneProps} />)
    expect(screen.getByText(BRIEFING_EMPTY_TITLE)).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Review & brief' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'File to store' })).not.toBeNull()
    expect(screen.getByText(FILE_TO_STORE_WARNING)).not.toBeNull()
  })

  it('renders the provisional markdown next to the actions', () => {
    render(
      <WhatsAppBriefingPane
        draft={{ ...draft, briefing_report_id: 'r1' }}
        report={report}
        {...paneProps}
      />,
    )
    expect(
      screen.getByText(/Provisional — WhatsApp hour briefing/),
    ).not.toBeNull()
    expect(screen.getByText(/3 houses flooded/)).not.toBeNull()
  })

  it('tells the officer when the briefing is stale vs the rail', () => {
    render(
      <WhatsAppBriefingPane
        draft={{
          ...draft,
          briefing_report_id: 'r1',
          briefing_stale: true,
        }}
        report={report}
        {...paneProps}
      />,
    )
    expect(screen.getByText(BRIEFING_STALE_COPY)).not.toBeNull()
  })

  it('disables File and Review when nothing is included', () => {
    render(
      <WhatsAppBriefingPane
        draft={draft}
        includedCount={0}
        briefingPending={false}
        promotePending={false}
        onReview={vi.fn()}
        onPromote={vi.fn()}
      />,
    )
    expect(
      (screen.getByRole('button', { name: 'File to store' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
    expect(
      (screen.getByRole('button', { name: 'Review & brief' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('opens review from Review & brief', () => {
    const onReview = vi.fn()
    render(
      <WhatsAppBriefingPane
        draft={draft}
        includedCount={1}
        briefingPending={false}
        promotePending={false}
        onReview={onReview}
        onPromote={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Review & brief' }))
    expect(onReview).toHaveBeenCalledTimes(1)
  })
})
