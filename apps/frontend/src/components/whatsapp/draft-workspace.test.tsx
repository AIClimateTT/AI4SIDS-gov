// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import type { UIMessage } from '@tanstack/ai-react'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const sendMessage = vi.fn()

const { mockState, draft } = vi.hoisted(() => {
  const mockState = {
    messages: [] as UIMessage[],
    isLoading: false,
  }
  const draft = {
    id: 4,
    draft_id: 4,
    filename: 'pasted.txt',
    source_kind: 'paste' as const,
    as_at: '2026-08-15T16:00:00',
    message_count: 1,
    pii_redacted: false,
    incidents: [
      {
        row_id: '1',
        corporation: null,
        community: null,
        street: null,
        incident_type: null,
        incident_summary: '3 houses flooded',
        event_date: null,
        injuries_count: null,
        deaths_count: null,
        source_index: 1,
        source_quote: '3 houses flooded',
        included: false,
      },
    ],
    logs: [],
    messages: [],
    manual_fields: [],
    missing: [
      { path: 'incident:1.corporation', message: 'Assign a corporation' },
    ],
    status: 'ready',
    error: null,
    created_at: '2026-08-15T16:00:00',
    updated_at: '2026-08-15T16:00:00',
  }
  return { mockState, draft }
})

vi.mock('@/components/chat/use-app-chat', () => ({
  useAppChat: () => ({
    messages: mockState.messages,
    sendMessage,
    isLoading: mockState.isLoading,
    error: undefined,
  }),
  createSseConnection: () => ({
    connect: async function* () {
      yield* []
    },
  }),
}))

vi.mock('@/lib/api/whatsapp', () => ({
  getWhatsAppDraft: async () => draft,
  updateWhatsAppDraft: async () => draft,
  generateWhatsAppBriefing: async () => ({
    id: 'r1',
    status: 'ok',
    markdown: '',
  }),
  promoteWhatsAppDraft: async () => ({ submissions: [] }),
}))

import {
  WHATSAPP_COMPOSER_PLACEHOLDER,
  WhatsAppDraftWorkspace,
} from '@/components/whatsapp/draft-workspace'
import { whatsappKeys } from '@/lib/queries/whatsapp'

afterEach(() => {
  cleanup()
})

function renderWorkspace(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  queryClient.setQueryData(whatsappKeys.draft(draft.id), draft)
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('WhatsAppDraftWorkspace', () => {
  beforeEach(() => {
    sendMessage.mockReset()
    mockState.isLoading = false
    mockState.messages = []
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }),
    })
  })

  it('shows an empty-thread composer', () => {
    renderWorkspace(
      <WhatsAppDraftWorkspace draftId={4} onNewExtract={vi.fn()} />,
    )
    expect(
      screen.getByPlaceholderText(WHATSAPP_COMPOSER_PLACEHOLDER),
    ).not.toBeNull()
  })
})
