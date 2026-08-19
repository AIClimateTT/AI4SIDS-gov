import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { CORPORATION_LABELS, type CanonicalCorporation } from '@/lib/corporations'

export type ComposerProps = {
  corporation: CanonicalCorporation
  createSession: (input: { corporation: string }) => Promise<{ id: number }>
  onStarted: (sessionId: number, firstMessage: string) => void
}

// Filing by conversation is the primary path (see the plan brief): an
// officer opens the app and just starts typing. This textarea is the whole
// job -- it creates an event-less session and hands the typed text off as
// the opening turn. Attaching an event, adding rows by hand, and CSV upload
// are all secondary and live elsewhere on the home page.
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
    <div className="w-full space-y-2">
      <Textarea
        autoFocus
        rows={3}
        value={value}
        disabled={pending}
        placeholder={`What's happening in ${CORPORATION_LABELS[corporation]}?`}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            start()
          }
        }}
      />
      <div className="flex justify-end">
        <Button type="button" disabled={pending || !value.trim()} onClick={start}>
          {pending ? 'Starting…' : 'Start'}
        </Button>
      </div>
    </div>
  )
}
