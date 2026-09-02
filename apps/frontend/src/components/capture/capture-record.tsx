import { useEffect, useRef, useState } from 'react'

import { EventChip } from '@/components/capture/event-chip'
import { IncidentCard } from '@/components/capture/incident-card'
import { LogCard } from '@/components/capture/log-card'
import { AlertLevelBadge } from '@/components/shared'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Textarea } from '@/components/ui/textarea'
import { withManual } from '@/lib/capture-paths'
import { workingSetTallies } from '@/lib/capture-tallies'
import {
  ALERT_LEVELS,
  formToCaptureIncident,
  formToCaptureLog,
  nextRowId,
  toDatetimeLocal,
  toIsoDateTime,
} from '@/lib/capture-mapping'
import { formatConstant } from '@/lib/format-constant'
import { formatWhen } from '@/lib/format-when'
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
  onReview?: () => void
}

// A literal [] default prop allocates a brand-new array every render,
// which defeats memoization on anything downstream that compares `events`
// by reference. Module-scope keeps identity stable across renders.
const EMPTY_EVENTS: EventSummary[] = []

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
  events = EMPTY_EVENTS,
  disabled,
  pending,
  onSave,
  onReview,
}: CaptureRecordProps) {
  const alertMissing = session.missing.find(
    (item) => item.path === 'alert_level',
  )
  const asAtMissing = session.missing.find((item) => item.path === 'as_at')

  const saveIncidents = (incidents: CaptureSessionUpdate['incidents']) =>
    onSave(payloadOf(session, { incidents }))
  const saveLogs = (logs: CaptureSessionUpdate['logs']) =>
    onSave(payloadOf(session, { logs }))

  return (
    <div className="flex h-full min-h-0 flex-col">
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
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground">
            Situation
          </h2>
          <SituationField
            label="Situation overview"
            value={session.situation_overview}
            placeholder="Add a situation overview…"
            disabled={disabled}
            onCommit={(value) =>
              onSave(
                payloadOf(session, {
                  situation_overview: value,
                  manual_fields: withManual(
                    session.manual_fields,
                    'situation_overview',
                  ),
                }),
              )
            }
          />
          <SituationField
            label="Present activity"
            value={session.present_activity}
            placeholder="What is happening now…"
            disabled={disabled}
            onCommit={(value) =>
              onSave(
                payloadOf(session, {
                  present_activity: value,
                  manual_fields: withManual(
                    session.manual_fields,
                    'present_activity',
                  ),
                }),
              )
            }
          />
        </section>

        <TallyStrip incidents={session.incidents} />

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
            <p className="text-sm text-muted-foreground">
              No incidents captured yet.
            </p>
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
                    manual_fields: withManualPaths(
                      session.manual_fields,
                      paths,
                    ),
                  }),
                )
              }}
              onRemove={() =>
                saveIncidents(
                  session.incidents.filter(
                    (row) => row.row_id !== incident.row_id,
                  ),
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
            <p className="text-sm text-muted-foreground">
              No situation logs captured yet.
            </p>
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
                    logs: session.logs.map((row) =>
                      row.row_id === log.row_id ? next : row,
                    ),
                    manual_fields: withManualPaths(
                      session.manual_fields,
                      paths,
                    ),
                  }),
                )
              }}
              onRemove={() =>
                // Removal is by row_id, never index -- indices shift as rows
                // are added and removed, but row_id is stable for the life
                // of the session (F3).
                saveLogs(
                  session.logs.filter((row) => row.row_id !== log.row_id),
                )
              }
            />
          ))}
        </section>
      </div>

      {onReview ? (
        <div className="sticky bottom-0 flex flex-wrap items-center justify-end gap-2 border-t bg-background px-4 py-3">
          <Button
            type="button"
            disabled={disabled || pending}
            onClick={onReview}
          >
            Review & file
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function SituationField({
  label,
  value,
  placeholder,
  disabled,
  onCommit,
}: {
  label: string
  value: string | null
  placeholder: string
  disabled?: boolean
  onCommit: (value: string | null) => void
}) {
  const serverValue = value ?? ''
  const [draft, setDraft] = useState(serverValue)
  // Whether the officer's cursor is in this box right now. A ref, not state:
  // it gates the sync below without being a dependency of it, so losing focus
  // can never itself re-run the sync -- which would revert the officer's text
  // to the server value in the window before their commit round-trips.
  const hasFocus = useRef(false)

  useEffect(() => {
    // Every chat turn saves and refetches the session, and a turn can extract
    // a situation overview into this very field -- while the officer may be
    // mid-sentence in it. Adopting the server value unconditionally erased
    // what they had typed: the edit loss 46e4d8e fixed once, reintroduced by
    // the pane -> record rewrite.
    //
    // Focus is the right guard because it is the actual invariant: never pull
    // text out from under a cursor. An unfocused field still follows the
    // server, so chat extraction still lands on fields nobody is holding.
    if (hasFocus.current) return
    setDraft(serverValue)
  }, [serverValue])

  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <Textarea
        aria-label={label}
        value={draft}
        placeholder={placeholder}
        disabled={disabled}
        rows={2}
        onChange={(event) => setDraft(event.target.value)}
        onFocus={() => {
          hasFocus.current = true
        }}
        onBlur={() => {
          hasFocus.current = false
          const next = draft.trim() || null
          const previous = value?.trim() || null
          if (next === previous) return
          onCommit(next)
        }}
      />
    </label>
  )
}

function TallyStrip({ incidents }: { incidents: CaptureSession['incidents'] }) {
  const tallies = workingSetTallies(incidents)
  const parts = [
    `${tallies.incidents} ${tallies.incidents === 1 ? 'incident' : 'incidents'}`,
  ]
  if (tallies.injuries > 0) parts.push(`${tallies.injuries} injured`)
  if (tallies.deaths > 0) parts.push(`${tallies.deaths} dead`)
  if (tallies.unknownCasualties > 0) {
    parts.push(
      tallies.unknownCasualties === 1
        ? '1 with unknown casualties'
        : `${tallies.unknownCasualties} with unknown casualties`,
    )
  }
  if (tallies.reliefSupplied > 0)
    parts.push(`${tallies.reliefSupplied} relief given`)
  if (tallies.furtherAssessment > 0) {
    parts.push(`${tallies.furtherAssessment} need assessment`)
  }

  return <p className="text-sm">{parts.join(' · ')}</p>
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
            variant={missing ? 'outline' : 'ghost'}
            size="sm"
            disabled={disabled}
            // When the level is missing the trigger's own text says so; when
            // it is set the trigger is a badge, whose word alone ("Yellow")
            // does not say what it is the level of.
            aria-label={
              missing ? undefined : `Alert level: ${formatConstant(value)}`
            }
          />
        }
      >
        {/* The chip that sets the level is the one place the level was still
            rendered as plain text, so the officer choosing it saw less than
            anyone reading it downstream. */}
        {missing ? missing.message : <AlertLevelBadge level={value} />}
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
        {missing ? missing.message : formatWhen(value)}
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
