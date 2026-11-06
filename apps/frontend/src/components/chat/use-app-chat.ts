import { useChat, fetchServerSentEvents } from '@tanstack/ai-react'
import type { ConnectionAdapter, UIMessage } from '@tanstack/ai-react'

import { proactiveRefresh } from '@/lib/auth/refresh'
import { getAccessToken } from '@/lib/auth/storage'

export type ChatCustomEvent = {
  name: string
  value: unknown
}

export function createSseConnection(
  path: string,
  forwardedProps?: Record<string, unknown>,
): ConnectionAdapter {
  const base =
    (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'
  const url = `${base.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  // A function, not a value: the token is read per request, the way the axios
  // client does, so a long-lived chat keeps working after a refresh.
  return fetchServerSentEvents(url, async () => {
    const token = await proactiveRefresh(getAccessToken(), url)
    return {
      ...(forwardedProps ? { body: forwardedProps } : {}),
      ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
    }
  })
}

export function useAppChat({
  connection,
  initialMessages,
  onCustomEvent,
  threadId,
}: {
  connection: ConnectionAdapter
  initialMessages?: UIMessage[]
  onCustomEvent?: (event: ChatCustomEvent) => void
  threadId?: string
}) {
  return useChat({
    connection,
    initialMessages,
    threadId,
    queue: 'drop',
    onChunk: (chunk) => {
      if (!chunk || typeof chunk !== 'object' || !('type' in chunk)) return
      if (chunk.type !== 'CUSTOM') return
      const custom = chunk as { name?: unknown; value?: unknown }
      if (typeof custom.name !== 'string') return
      onCustomEvent?.({ name: custom.name, value: custom.value })
    },
  })
}
