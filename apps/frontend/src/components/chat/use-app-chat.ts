import { useChat, fetchServerSentEvents } from '@tanstack/ai-react'
import type { ConnectionAdapter, UIMessage } from '@tanstack/ai-react'

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
  return fetchServerSentEvents(
    url,
    forwardedProps ? { body: forwardedProps } : undefined,
  )
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
