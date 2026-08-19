import { useState } from 'react'

import { EventChip } from '@/components/capture/event-chip'
import { IncidentCard } from '@/components/capture/incident-card'
import { LogCard } from '@/components/capture/log-card'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import { withManual } from '@/lib/capture-paths'
import {
  ALERT_LEVELS,
  formToCaptureIncident,
  formToCaptureLog,
  nextRowId,
  toDatetimeLocal,
  toIsoDateTime,
} from '@/lib/capture-mapping'
import { formatConstant } from '@/lib/format-constant'
import type {
  CaptureMissingField,
  CaptureSession,
  CaptureSessionUpdate,
  EventSummary,
} from '@/types/dmcu'

export type CaptureRecordProps = {
  session: CaptureSession
  events?: EventSummary[]
  disabled?: boolean
  pending?: boolean
  onSave: (payload: CaptureSessionUpdate) => void
  onReview: () => void
}

// Every edit saves immediately -- one contract, replacing the old form
// pane's separate "Save" button for the situation header. payloadOf keeps
// whatever the patch does not touch, so a single-field edit (e.g. alert
// level) never clobbers incidents/logs/manual_fields the officer already
// has in the record.
function payloadOf(
  session: CaptureSession,
  patch: Partial<CaptureSessionUpdate>,
): CaptureSessionUpdate {
  return {
    as_at: patch.as_at ?? session.as_at,
    alert_level: patch.alert_level ?? session.alert_level,
    present_activity:
      patch.present_activity !== undefined
        ? patch.present_activity
        : session.present_activity,
    situation_overview:
      patch.situation_overview !== undefined
        ? patch.situation_overview
        : session.situation_overview,
    incidents: patch.incidents ?? session.incidents,
    logs: patch.logs ?? session.logs,
    manual_fields: patch.manual_fields ?? session.manual_fields,
  }
}

// Missing-field paths are array-indexed (`incidents[0].event_date`), not
// row-id keyed, so a card's missing entries are whatever share its position
// in the array -- not its row_id.
function missingFor(
  missing: CaptureMissingField[],
  collection: 'incidents' | 'logs',
  index: number,
): CaptureMissingField[] {
  const prefix = `${collection}[${index}].`
  return missing.filter((item) => item.path.startsWith(prefix))
}

function withManualPaths(manual: string[], paths: string[]): string[] {
  return paths.reduce((next, path) => withManual(next, path), manual)
}

export function CaptureRecord({
  session,
  events = [],
  disabled,
  pending,
  onSave,
  onReview,
}: CaptureRecordProps) {
  const alertMissing = session.missing.find((item) => item.path === 'alert_level')
  const asAtMissing = session.missing.find((item) => item.path === 'as_at')

  const saveIncidents = (incidents: CaptureSessionUpdate['incidents']) =>
    onSave(payloadOf(session, { incidents }))
  const saveLogs = (logs: CaptureSessionUpdate['logs']) =>
    onSave(payloadOf(session, { logs }))

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
        <EventChip session={session} events={events} disabled={disabled} />
        <AlertLevelChip
          value={session.alert_level}
          missing={alertMissing}
          disabled={disabled}
          onChange={(value) =>
            onSave(
              payloadOf(session, {
                alert_level: value,
                manual_fields: withManual(session.manual_fields, 'alert_level'),
              }),
            )
          }
        />
        <AsAtChip
          value={session.as_at}
          missing={asAtMissing}
          disabled={disabled}
          onChange={(value) =>
            onSave(
              payloadOf(session, {
                as_at: value,
                manual_fields: withManual(session.manual_fields, 'as_at'),
              }),
            )
          }
        />
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Incidents ({session.incidents.length})
            </h2>
            {!disabled ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  const rowId = nextRowId(session.incidents)
                  const blank = formToCaptureIncident(
                    {
                      community: '',
                      street: '',
                      incident_type: '',
                      incident_summary: '',
                      event_date: '',
                      injuries_count: '',
                      deaths_count: '',
                    },
                    rowId,
                  )
                  saveIncidents([...session.incidents, blank])
                }}
              >
                + Add manually
              </Button>
            ) : null}
          </div>
          {session.incidents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No incidents captured yet.</p>
          ) : null}
          {session.incidents.map((incident, index) => (
            <IncidentCard
              key={incident.row_id}
              incident={incident}
              missing={missingFor(session.missing, 'incidents', index)}
              disabled={disabled}
              onEdit={(next, paths) => {
                onSave(
                  payloadOf(session, {
                    incidents: session.incidents.map((row) =>
                      row.row_id === incident.row_id ? next : row,
                    ),
                    manual_fields: withManualPaths(session.manual_fields, paths),
                  }),
                )
              }}
              onRemove={() =>
                saveIncidents(
                  session.incidents.filter((row) => row.row_id !== incident.row_id),
                )
              }
            />
          ))}
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Situation logs ({session.logs.length})
            </h2>
            {!disabled ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  const rowId = nextRowId(session.logs)
                  const blank = formToCaptureLog(
                    {
                      category: '',
                      statement: '',
                      item: '',
                      quantity: '',
                      unit: '',
                      status: 'none',
                    },
                    rowId,
                  )
                  saveLogs([...session.logs, blank])
                }}
              >
                + Add manually
              </Button>
            ) : null}
          </div>
          {session.logs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No situation logs captured yet.</p>
          ) : null}
          {session.logs.map((log, index) => (
            <LogCard
              key={log.row_id}
              log={log}
              missing={missingFor(session.missing, 'logs', index)}
              disabled={disabled}
              onEdit={(next, paths) => {
                onSave(
                  payloadOf(session, {
                    logs: session.logs.map((row) => (row.row_id === log.row_id ? next : row)),
                    manual_fields: withManualPaths(session.manual_fields, paths),
                  }),
                )
              }}
              onRemove={() =>
                // Removal is by row_id, never index -- indices shift as rows
                // are added and removed, but row_id is stable for the life
                // of the session (F3).
                saveLogs(session.logs.filter((row) => row.row_id !== log.row_id))
              }
            />
          ))}
        </section>
      </div>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-2 border-t bg-background px-4 py-3">
        <p className="text-sm text-muted-foreground">
          {session.incidents.length} incidents · {session.logs.length} logs ·{' '}
          {session.missing.length} details needed
        </p>
        <Button type="button" disabled={disabled || pending} onClick={onReview}>
          Review & file
        </Button>
      </div>
    </div>
  )
}

function AlertLevelChip({
  value,
  missing,
  disabled,
  onChange,
}: {
  value: string
  missing?: CaptureMissingField
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant={missing ? 'outline' : 'secondary'}
            size="sm"
            disabled={disabled}
          />
        }
      >
        {missing ? missing.message : formatConstant(value)}
      </PopoverTrigger>
      <PopoverContent className="w-56">
        <PopoverHeader>
          <PopoverTitle>Alert level</PopoverTitle>
        </PopoverHeader>
        <select
          aria-label="Alert level"
          className="h-8 rounded-md border px-2 text-sm"
          value={value}
          disabled={disabled}
          onChange={(event) => {
            onChange(event.target.value)
            setOpen(false)
          }}
        >
          {ALERT_LEVELS.map((level) => (
            <option key={level} value={level}>
              {formatConstant(level)}
            </option>
          ))}
        </select>
      </PopoverContent>
    </Popover>
  )
}

function AsAtChip({
  value,
  missing,
  disabled,
  onChange,
}: {
  value: string
  missing?: CaptureMissingField
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant={missing ? 'outline' : 'secondary'}
            size="sm"
            disabled={disabled}
          />
        }
      >
        {missing ? missing.message : toDatetimeLocal(value).replace('T', ' ')}
      </PopoverTrigger>
      <PopoverContent className="w-64">
        <PopoverHeader>
          <PopoverTitle>As at</PopoverTitle>
        </PopoverHeader>
        <input
          aria-label="As at"
          type="datetime-local"
          className="h-8 rounded-md border px-2 text-sm"
          defaultValue={toDatetimeLocal(value)}
          disabled={disabled}
          onChange={(event) => {
            if (!event.target.value) return
            onChange(toIsoDateTime(event.target.value))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
