// The model may talk about which event this is; it never sets event_id.
// Cross-submission supersession is event-scoped, so a wrong attachment
// silently merges one storm's record into another's.
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useAttachCaptureEvent } from '@/lib/queries/capture'
import type { AttachEventBody, CaptureSession, EventSummary } from '@/types/dmcu'

export type EventChipProps = {
  session: CaptureSession
  events: EventSummary[]
  disabled?: boolean
}

const HAZARD_TYPES = ['flood', 'landslide', 'wind', 'fire', 'other'] as const

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10)
}

export function EventChip({ session, events, disabled }: EventChipProps) {
  const attach = useAttachCaptureEvent()
  const [open, setOpen] = useState(false)

  const attachedEvent =
    session.event_id != null
      ? events.find((event) => event.id === session.event_id)
      : undefined
  const running = events.filter((event) => event.ended_at === null)

  const attachTo = (body: AttachEventBody) => {
    attach.mutate({ id: session.id, body })
    setOpen(false)
  }

  if (attachedEvent) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <Button type="button" variant="secondary" size="sm" disabled={disabled} />
          }
        >
          {attachedEvent.title}
        </PopoverTrigger>
        <PopoverContent>
          <PopoverHeader>
            <PopoverTitle>Change event</PopoverTitle>
          </PopoverHeader>
          <div className="flex flex-col gap-1">
            {events.map((event) => (
              <Button
                key={event.id}
                type="button"
                variant={event.id === session.event_id ? 'secondary' : 'ghost'}
                size="sm"
                className="justify-start"
                onClick={() => attachTo({ event_id: event.id })}
              >
                {event.title}
              </Button>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    )
  }

  if (running.length === 1) {
    const only = running[0]
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => attachTo({ event_id: only.id })}
      >
        {`Attach to "${only.title}"?`}
      </Button>
    )
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        No event
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Attach an event</SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-4 overflow-y-auto px-4 pb-4">
            {running.length > 0 ? (
              <div className="flex flex-col gap-1">
                {running.map((event) => (
                  <Button
                    key={event.id}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="justify-start"
                    onClick={() => attachTo({ event_id: event.id })}
                  >
                    {event.title}
                  </Button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No running events for this corporation.
              </p>
            )}
            <NewEventForm onCreate={attachTo} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}

function NewEventForm({
  onCreate,
}: {
  onCreate: (body: Extract<AttachEventBody, { title: string }>) => void
}) {
  const [title, setTitle] = useState('')
  const [hazardType, setHazardType] = useState<string>(HAZARD_TYPES[0])
  const [startedAt, setStartedAt] = useState(todayIsoDate())

  return (
    <form
      className="flex flex-col gap-3 border-t pt-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (!title.trim()) return
        onCreate({ title: title.trim(), hazard_type: hazardType, started_at: startedAt })
      }}
    >
      <p className="text-sm font-medium">New event</p>
      <label className="flex flex-col gap-1 text-sm">
        Title
        <input
          className="h-8 rounded-md border px-2 text-sm"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Hazard type
        <select
          className="h-8 rounded-md border px-2 text-sm"
          value={hazardType}
          onChange={(event) => setHazardType(event.target.value)}
        >
          {HAZARD_TYPES.map((value) => (
            <option key={value} value={value}>
              {value.charAt(0).toUpperCase() + value.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Start date
        <input
          type="date"
          className="h-8 rounded-md border px-2 text-sm"
          value={startedAt}
          onChange={(event) => setStartedAt(event.target.value)}
        />
      </label>
      <Button type="submit" size="sm" disabled={!title.trim()}>
        Create and attach
      </Button>
    </form>
  )
}
