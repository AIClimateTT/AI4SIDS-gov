import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAttachCaptureEvent } from '@/lib/queries/capture'
import {
  EVENT_HAZARD_TYPES,
  proposeEventFromSession,
} from '@/lib/propose-event'
import type { AttachEventBody, CaptureSession, EventSummary } from '@/types/dmcu'

export type EventConfirmBannerProps = {
  session: CaptureSession
  events: EventSummary[]
  disabled?: boolean
}

export function EventConfirmBanner({
  session,
  events,
  disabled,
}: EventConfirmBannerProps) {
  const attach = useAttachCaptureEvent()
  const proposal = proposeEventFromSession(session)
  const running = events.filter((event) => event.ended_at === null)
  const [dirty, setDirty] = useState(false)
  const [title, setTitle] = useState(proposal.title)
  const [hazardType, setHazardType] = useState(proposal.hazard_type)
  const [startedAt, setStartedAt] = useState(proposal.started_at)

  useEffect(() => {
    if (dirty) return
    setTitle(proposal.title)
    setHazardType(proposal.hazard_type)
    setStartedAt(proposal.started_at)
  }, [dirty, proposal.hazard_type, proposal.started_at, proposal.title])

  const busy = disabled || attach.isPending

  const submit = (body: AttachEventBody) => {
    attach.mutate({ id: session.id, body })
  }

  const confirmNew = () => {
    const cleaned = title.trim()
    if (!cleaned) return
    submit({ title: cleaned, hazard_type: hazardType, started_at: startedAt })
  }

  return (
    <section
      aria-label="Confirm event"
      className="rounded-lg border border-amber-700/25 bg-amber-50 px-3 py-3 text-sm dark:bg-amber-950/40"
    >
      <p className="font-medium">Confirm which event this sitrep belongs to</p>
      <p className="mt-1 text-muted-foreground">
        Chat stays open. You cannot issue incidents until this is confirmed.
      </p>

      {running.length > 0 ? (
        <div className="mt-3 flex flex-col gap-1">
          {running.map((event) => (
            <Button
              key={event.id}
              type="button"
              variant="secondary"
              size="sm"
              className="justify-start"
              disabled={busy}
              onClick={() => submit({ event_id: event.id })}
            >
              {`This is part of ${event.title}`}
            </Button>
          ))}
        </div>
      ) : null}

      <form
        className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          confirmNew()
        }}
      >
        <div className="space-y-1">
          <Label htmlFor="event-title">
            {running.length > 0 ? 'Or start a new event' : 'Event title'}
          </Label>
          <Input
            id="event-title"
            value={title}
            disabled={busy}
            onChange={(event) => {
              setDirty(true)
              setTitle(event.target.value)
            }}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="event-hazard">Hazard</Label>
          <select
            id="event-hazard"
            className="h-8 w-full rounded-md border px-2 text-sm"
            value={hazardType}
            disabled={busy}
            onChange={(event) => {
              setDirty(true)
              setHazardType(event.target.value as typeof hazardType)
            }}
          >
            {EVENT_HAZARD_TYPES.map((value) => (
              <option key={value} value={value}>
                {value.charAt(0).toUpperCase() + value.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="event-started">Start date</Label>
          <Input
            id="event-started"
            type="date"
            value={startedAt}
            disabled={busy}
            onChange={(event) => {
              setDirty(true)
              setStartedAt(event.target.value)
            }}
          />
        </div>
        <div className="sm:col-span-3">
          <Button type="submit" size="sm" disabled={busy || !title.trim()}>
            Confirm event
          </Button>
        </div>
      </form>
    </section>
  )
}
