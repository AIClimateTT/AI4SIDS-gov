// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WhatsAppDraftRecord } from '@/components/whatsapp/draft-record'
import type { WhatsAppDraft } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const draft: WhatsAppDraft = {
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
  created_at: '2026-08-15T16:00:00',
  updated_at: '2026-08-15T16:00:00',
}

describe('WhatsAppDraftRecord', () => {
  it('records a manual path when the include toggle is clicked', () => {
    const onSave = vi.fn()
    render(<WhatsAppDraftRecord draft={draft} onSave={onSave} />)

    fireEvent.click(screen.getByRole('checkbox', { name: /include this incident/i }))

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        manual_fields: ['incident:1.included'],
        incidents: [expect.objectContaining({ included: false, row_id: '1' })],
      }),
    )
  })

  it('keys the corporation control by row_id', () => {
    render(<WhatsAppDraftRecord draft={draft} onSave={vi.fn()} />)
    expect(screen.getByLabelText('Corporation').id).toBe('incident-corp-1')
  })
})
