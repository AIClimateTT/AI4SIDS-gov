import { describe, expect, it } from 'vitest'

import { messageText, toChatMessages } from '@/components/chat/messages'

describe('toChatMessages', () => {
  it('maps role and content into UIMessage text parts', () => {
    const messages = toChatMessages([
      { role: 'assistant', content: 'Tell me what is happening.' },
      { role: 'user', content: '5 houses flooded in Petit Valley.' },
    ])

    expect(messages).toEqual([
      {
        id: 'seed-0',
        role: 'assistant',
        parts: [{ type: 'text', content: 'Tell me what is happening.' }],
      },
      {
        id: 'seed-1',
        role: 'user',
        parts: [{ type: 'text', content: '5 houses flooded in Petit Valley.' }],
      },
    ])
  })
})

describe('messageText', () => {
  it('joins text parts', () => {
    expect(
      messageText({
        id: '1',
        role: 'assistant',
        parts: [
          { type: 'text', content: 'Captured: ' },
          { type: 'text', content: '5 houses.' },
        ],
      }),
    ).toBe('Captured: 5 houses.')
  })
})
