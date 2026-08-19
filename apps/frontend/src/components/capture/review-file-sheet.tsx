import { useMemo } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useIsMobile } from '@/hooks/use-mobile'
import { formatConstant } from '@/lib/format-constant'
import { cn } from '@/lib/utils'
import type { CaptureIncident, CaptureSession } from '@/types/dmcu'

export type ReviewFileSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  session: CaptureSession
  filing: boolean
  onFile: () => void
  /** Resolved by the caller from the events list it already has loaded.
   * Falls back to a plain "Event N" label (never "#N" -- that reads as a
   * report number, which is exactly what this sheet must not name). */
  eventTitle?: string | null
}

function normalize(value: string | null): string {
  return (value ?? '').trim().toLowerCase()
}

// The capture pipeline can, in one specific case, produce a duplicate row:
// if the model re-emits a hand-corrected incident but omits its row_id, the
// row is re-added under a fresh id while the original is also restored.
// We deliberately allow that rather than risk silently losing an
// officer-entered incident -- a visible duplicate is recoverable, a
// deletion is not. This is where a human is supposed to catch it, so flag
// incidents that share either an incident_summary or a
// community+type+date combination with another incident about to be filed.
export function detectDuplicateIncidents(incidents: CaptureIncident[]): Set<string> {
  const bySummary = new Map<string, string[]>()
  const byComposite = new Map<string, string[]>()

  for (const incident of incidents) {
    const summary = normalize(incident.incident_summary)
    if (summary) {
      bySummary.set(summary, [...(bySummary.get(summary) ?? []), incident.row_id])
    }

    const community = normalize(incident.community)
    const type = normalize(incident.incident_type)
    const date = normalize(incident.event_date)
    if (community && type && date) {
      const key = `${community}|${type}|${date}`
      byComposite.set(key, [...(byComposite.get(key) ?? []), incident.row_id])
    }
  }

  const duplicates = new Set<string>()
  for (const rowIds of [...bySummary.values(), ...byComposite.values()]) {
    if (rowIds.length > 1) rowIds.forEach((rowId) => duplicates.add(rowId))
  }
  return duplicates
}

export function ReviewFileSheet({
  open,
  onOpenChange,
  session,
  filing,
  onFile,
  eventTitle,
}: ReviewFileSheetProps) {
  const isMobile = useIsMobile()
  const duplicateRowIds = useMemo(
    () => detectDuplicateIncidents(session.incidents),
    [session.incidents],
  )

  // Client-side mirror of the backend's 400: incidents with no event to
  // attach to are rejected there, so the button is disabled here with the
  // same reason stated inline rather than letting the officer hit file and
  // learn about it from an error toast.
  const blockedNoEvent = session.event_id === null && session.incidents.length > 0
  const fileDisabled = filing || blockedNoEvent

  const eventLabel =
    eventTitle ?? (session.event_id != null ? `Event ${session.event_id}` : 'No event attached')

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isMobile ? 'bottom' : 'right'}
        className="flex h-[85svh] flex-col gap-0 p-0 md:h-full"
      >
        <SheetHeader className="border-b">
          <SheetTitle>Review before filing</SheetTitle>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Event</dt>
              <dd>{eventLabel}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Alert level</dt>
              <dd>{formatConstant(session.alert_level)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">As at</dt>
              <dd>{new Date(session.as_at).toLocaleString()}</dd>
            </div>
          </dl>

          <p className="text-sm font-medium">
            {session.incidents.length} incident{session.incidents.length === 1 ? '' : 's'} ·{' '}
            {session.logs.length} log{session.logs.length === 1 ? '' : 's'}
          </p>

          {duplicateRowIds.size > 0 ? (
            <div className="rounded-md border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {duplicateRowIds.size} incident{duplicateRowIds.size === 1 ? '' : 's'} look
              {duplicateRowIds.size === 1 ? 's' : ''} like duplicates — check before filing
            </div>
          ) : null}

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground">
              Incidents ({session.incidents.length})
            </h3>
            {session.incidents.length === 0 ? (
              <p className="text-sm text-muted-foreground">No incidents captured.</p>
            ) : null}
            {session.incidents.map((incident) => (
              <div
                key={incident.row_id}
                className={cn(
                  'space-y-1 rounded-md border px-3 py-2 text-sm',
                  duplicateRowIds.has(incident.row_id) && 'border-destructive/60 bg-destructive/5',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{incident.incident_summary || 'Untitled incident'}</p>
                  {duplicateRowIds.has(incident.row_id) ? (
                    <Badge variant="destructive">Possible duplicate</Badge>
                  ) : null}
                </div>
                <p className="text-muted-foreground">
                  {[
                    incident.community,
                    incident.incident_type ? formatConstant(incident.incident_type) : null,
                  ]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </p>
              </div>
            ))}
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground">
              Situation logs ({session.logs.length})
            </h3>
            {session.logs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No situation logs captured.</p>
            ) : null}
            {session.logs.map((log) => (
              <div key={log.row_id} className="space-y-1 rounded-md border px-3 py-2 text-sm">
                <p className="font-medium">{formatConstant(log.category)}</p>
                <p className="text-muted-foreground">{log.statement || '—'}</p>
              </div>
            ))}
          </section>

          {session.missing.length > 0 ? (
            <div className="rounded-md border border-amber-500/50 bg-amber-500/5 px-3 py-2 text-sm">
              <p className="font-medium">
                {session.missing.length} detail{session.missing.length === 1 ? '' : 's'} still
                needed
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {session.missing.map((item) => (
                  <li key={item.path}>{item.message}</li>
                ))}
              </ul>
              <p className="mt-1 text-muted-foreground">
                Filing is still allowed with these gaps -- they can be filled in later.
              </p>
            </div>
          ) : null}
        </div>

        <SheetFooter className="border-t">
          {blockedNoEvent ? (
            <p className="text-sm text-destructive">
              Incidents must be attached to an event before filing.
            </p>
          ) : null}
          <Button type="button" disabled={fileDisabled} onClick={onFile}>
            {filing ? 'Filing…' : 'File situation report'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
