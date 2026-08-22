// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { UIMessage } from '@tanstack/ai-react'

const sendMessage = vi.fn()

const mockState = vi.hoisted(() => ({
  messages: [] as UIMessage[],
  isLoading: false,
}))

vi.mock('@/components/chat/use-app-chat', () => ({
  useAppChat: () => ({
    messages: mockState.messages,
    sendMessage,
    isLoading: mockState.isLoading,
    error: undefined,
  }),
}))

import { ChatThread } from '@/components/chat/chat-thread'

const connection = {
  connect: async function* () {
    yield* []
  },
} as never

describe('ChatThread', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    sendMessage.mockReset()
    mockState.isLoading = false
    mockState.messages = [
      {
        id: 'seed-0',
        role: 'assistant',
        parts: [{ type: 'text', content: 'Tell me what is happening.' }],
      },
    ]
  })

  it('renders seeded messages and sends from the composer', () => {
    render(
      <ChatThread
        connection={connection}
        initialMessages={mockState.messages}
        placeholder="Describe what happened…"
      />,
    )

    expect(screen.getByText('Tell me what is happening.')).not.toBeNull()
    const composer = screen.getByPlaceholderText('Describe what happened…')
    fireEvent.change(composer, { target: { value: '5 houses flooded' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(sendMessage).toHaveBeenCalledWith('5 houses flooded')
  })

  it('shows a waiting state before the first assistant token', () => {
    mockState.isLoading = true
    mockState.messages = [
      {
        id: 'seed-0',
        role: 'assistant',
        parts: [{ type: 'text', content: 'Tell me what is happening.' }],
      },
      {
        id: 'u1',
        role: 'user',
        parts: [{ type: 'text', content: 'Flooding in Petit Valley.' }],
      },
    ]
    render(<ChatThread connection={connection} initialMessages={[]} />)
    expect(screen.getByRole('status').textContent).toMatch(/waiting|capturing|thinking/i)
  })
})
