// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { UIMessage } from '@tanstack/ai-react'

const sendMessage = vi.fn()

const mockState = vi.hoisted(() => ({
  messages: [] as UIMessage[],
  isLoading: false,
  queue: [] as { id: string; content: string; createdAt: number }[],
}))

vi.mock('@/components/chat/use-app-chat', () => ({
  useAppChat: () => ({
    messages: mockState.messages,
    sendMessage,
    isLoading: mockState.isLoading,
    queue: mockState.queue,
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
    mockState.queue = []
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

  it('keeps the composer open mid-turn and shows queued messages', () => {
    mockState.isLoading = true
    mockState.messages = [
      {
        id: 'u1',
        role: 'user',
        parts: [{ type: 'text', content: 'Flooding in Petit Valley.' }],
      },
      {
        id: 'a1',
        role: 'assistant',
        parts: [{ type: 'text', content: 'Confirmed.' }],
      },
    ]
    mockState.queue = [{ id: 'q1', content: 'Also a fallen tree.', createdAt: 0 }]
    render(
      <ChatThread
        connection={connection}
        initialMessages={[]}
        placeholder="Describe what happened…"
      />,
    )

    // The reply is on screen but the facts are not saved yet.
    expect(screen.getByRole('status').textContent).toMatch(/still capturing/i)
    expect(screen.getByText('Also a fallen tree.')).not.toBeNull()
    expect(screen.getByText(/queued/i)).not.toBeNull()

    const composer = screen.getByPlaceholderText('Describe what happened…')
    fireEvent.change(composer, { target: { value: 'And a landslide' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(sendMessage).toHaveBeenCalledWith('And a landslide')
  })
})
