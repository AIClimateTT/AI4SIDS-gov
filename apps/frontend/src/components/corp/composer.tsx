import { useState } from 'react'

import { ChatComposer } from '@/components/chat/chat-composer'
import { CORPORATION_LABELS, type CanonicalCorporation } from '@/lib/corporations'

export type ComposerProps = {
  corporation: CanonicalCorporation
  createSession: (input: { corporation: string }) => Promise<{ id: number }>
  onStarted: (sessionId: number, firstMessage: string) => void
}

// Filing by conversation is the primary path (see the plan brief): an
// officer opens the app and just starts typing. This composer creates an
// event-less session and hands the typed text off as the opening turn.
export function Composer({ corporation, createSession, onStarted }: ComposerProps) {
  const [value, setValue] = useState('')
  const [pending, setPending] = useState(false)

  const start = () => {
    const text = value.trim()
    if (!text || pending) return
    setPending(true)
    createSession({ corporation })
      .then((session) => {
        onStarted(session.id, text)
      })
      .catch(() => {
        // createSession's own mutation (useCreateCaptureSession) already
        // surfaces a toast on failure -- nothing else to do here.
      })
      .finally(() => setPending(false))
  }

  return (
    <ChatComposer
      autoFocus
      value={value}
      onChange={setValue}
      onSubmit={start}
      disabled={pending}
      placeholder={`What's happening in ${CORPORATION_LABELS[corporation]}?`}
    />
  )
}
