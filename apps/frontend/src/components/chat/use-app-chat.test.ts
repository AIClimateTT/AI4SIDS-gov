// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createSseConnection } from '@/components/chat/use-app-chat'

vi.mock('@/lib/auth/storage', async (original) => ({
  ...(await original<typeof import('@/lib/auth/storage')>()),
  getAccessToken: () => 'token-123',
}))
vi.mock('@/lib/auth/refresh', async (original) => ({
  ...(await original<typeof import('@/lib/auth/refresh')>()),
  proactiveRefresh: async (token: string | null) => token,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createSseConnection', () => {
  it('sends the login token, because the capture stream requires one', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('data: [DONE]\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const connection = createSseConnection('/capture/sessions/1/turns/stream')
    const stream = (
      connection as unknown as {
        connect: (messages: unknown[], data: unknown) => AsyncIterable<unknown>
      }
    ).connect([], {})
    for await (const _chunk of stream) {
      break
    }

    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token-123')
  })
})
