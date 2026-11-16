import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { ConnectionAdapter, UIMessage } from '@tanstack/ai-react'

import {
  ChatComposer,
  type ChatComposerAction,
} from '@/components/chat/chat-composer'
import { messageText } from '@/components/chat/messages'
import {
  useAppChat,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'
import { Bubble, BubbleContent } from '@/components/ui/bubble'
import { Message, MessageContent } from '@/components/ui/message'
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from '@/components/ui/message-scroller'

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
  actions?: ChatComposerAction[]
  /** Sticky strip above the composer — stays visible while the thread scrolls. */
  banner?: ReactNode
}

export function ChatThread({
  connection,
  initialMessages,
  disabled,
  onCustomEvent,
  placeholder = 'Describe what happened, or correct a figure…',
  threadId,
  autoSend,
  actions,
  banner,
}: ChatThreadProps) {
  const { messages, sendMessage, isLoading, error, queue } = useAppChat({
    connection,
    initialMessages,
    onCustomEvent,
    threadId,
  })
  const [draft, setDraft] = useState('')
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

  // The reply streams before the facts are written, so the run is still
  // going after the bubble fills in. Say so, or it looks finished.
  const saving = isLoading && !waiting
  const queued = queue ?? []

  function submit() {
    const cleaned = draft.trim()
    // Sending mid-turn is allowed: useAppChat queues it until the run settles.
    if (!cleaned || disabled) return
    void sendMessage(cleaned)
    setDraft('')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <MessageScrollerProvider autoScroll defaultScrollPosition="last-anchor">
        <MessageScroller className="min-h-0 flex-1">
          <MessageScrollerViewport>
            <MessageScrollerContent aria-busy={isLoading}>
              {messages.map((message) => (
                <ThreadMessage key={message.id} message={message} />
              ))}
              {waiting ? (
                <MessageScrollerItem messageId="capturing">
                  <Message>
                    <MessageContent>
                      <Bubble variant="muted">
                        <BubbleContent>
                          <p role="status">Capturing…</p>
                        </BubbleContent>
                      </Bubble>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ) : null}
              {saving ? (
                <MessageScrollerItem messageId="saving">
                  <p role="status" className="px-1 text-xs text-muted-foreground">
                    Still capturing — updating Facts…
                  </p>
                </MessageScrollerItem>
              ) : null}
              {queued.map((item) => (
                <MessageScrollerItem key={item.id} messageId={item.id}>
                  <Message align="end">
                    <MessageContent>
                      <Bubble variant="default" className="opacity-60">
                        <BubbleContent>
                          <p className="whitespace-pre-wrap">
                            {typeof item.content === 'string' ? item.content : ''}
                          </p>
                        </BubbleContent>
                      </Bubble>
                      <p className="text-right text-xs text-muted-foreground">
                        Queued — sends when this update is saved
                      </p>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ))}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>
      {banner ? <div className="shrink-0 pt-3">{banner}</div> : null}
      <div data-tour="thread-composer" className="shrink-0 pt-3">
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          disabled={disabled}
          placeholder={placeholder}
          error={error?.message}
          actions={actions}
        />
      </div>
    </div>
  )
}

function ThreadMessage({ message }: { message: UIMessage }) {
  const fromOfficer = message.role === 'user'
  return (
    <MessageScrollerItem
      messageId={message.id}
      scrollAnchor={fromOfficer}
    >
      <Message align={fromOfficer ? 'end' : 'start'}>
        <MessageContent>
          <Bubble variant={fromOfficer ? 'default' : 'muted'}>
            <BubbleContent>
              <p className="whitespace-pre-wrap">{messageText(message)}</p>
            </BubbleContent>
          </Bubble>
        </MessageContent>
      </Message>
    </MessageScrollerItem>
  )
}
