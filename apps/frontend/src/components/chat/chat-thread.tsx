import { useEffect, useRef, useState } from 'react'
import type { ConnectionAdapter, UIMessage } from '@tanstack/ai-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

import { messageText } from '@/components/chat/messages'
import {
  useAppChat,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'

type ChatThreadProps = {
  connection: ConnectionAdapter
  initialMessages?: UIMessage[]
  disabled?: boolean
  onCustomEvent?: (event: ChatCustomEvent) => void
  placeholder?: string
  threadId?: string
  /** Sent once, on mount, as the opening turn -- e.g. the text typed into
   * the home composer, handed off after the session is created. A ref
   * guards against a second send from React StrictMode's double effect. */
  autoSend?: string
}

export function ChatThread({
  connection,
  initialMessages,
  disabled,
  onCustomEvent,
  placeholder = 'Describe what happened, or correct a figure…',
  threadId,
  autoSend,
}: ChatThreadProps) {
  const { messages, sendMessage, isLoading, error } = useAppChat({
    connection,
    initialMessages,
    onCustomEvent,
    threadId,
  })
  const [draft, setDraft] = useState('')
  const list = useRef<HTMLDivElement>(null)
  const autoSent = useRef(false)

  useEffect(() => {
    if (!autoSend || autoSent.current) return
    autoSent.current = true
    void sendMessage(autoSend)
    // Only ever fires for the autoSend value this thread mounted with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const last = messages[messages.length - 1]
  const waiting =
    isLoading &&
    (last?.role === 'user' ||
      (last?.role === 'assistant' && !messageText(last)))

  useEffect(() => {
    const el = list.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, waiting])

  function submit() {
    const cleaned = draft.trim()
    if (!cleaned || disabled || isLoading) return
    void sendMessage(cleaned)
    setDraft('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={list} className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'rounded-lg px-3 py-2 text-sm',
              message.role === 'user'
                ? 'ml-8 bg-primary text-primary-foreground'
                : 'mr-8 bg-muted',
            )}
          >
            <p className="whitespace-pre-wrap">{messageText(message)}</p>
          </div>
        ))}
        {waiting ? (
          <div
            role="status"
            className="mr-8 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground"
          >
            Capturing…
          </div>
        ) : null}
      </div>
      <div className="mt-3 shrink-0 space-y-2">
        {error ? (
          <p className="text-sm text-destructive">{error.message}</p>
        ) : null}
        <Textarea
          value={draft}
          disabled={disabled || isLoading}
          rows={3}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        <div className="flex justify-end">
          <Button
            type="button"
            disabled={disabled || isLoading || !draft.trim()}
            onClick={submit}
          >
            {isLoading ? 'Capturing…' : 'Send'}
          </Button>
        </div>
      </div>
    </div>
  )
}
