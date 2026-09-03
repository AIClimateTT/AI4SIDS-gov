import { useEffect, useRef, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { useAppForm } from '@/hooks/form'
import { incidentPath } from '@/lib/capture-paths'
import {
  INCIDENT_TYPE_OPTIONS,
  casualtyOccurred,
  parseOptionalNumber,
} from '@/lib/capture-mapping'
import { casualtiesUnknown } from '@/lib/capture-tallies'
import { formatConstant } from '@/lib/format-constant'
import type { CaptureIncident, CaptureMissingField } from '@/types/dmcu'

export type IncidentCardProps = {
  incident: CaptureIncident
  missing: CaptureMissingField[]
  disabled?: boolean
  onEdit: (next: CaptureIncident, paths: string[]) => void
  onRemove: () => void
}

const incidentSchema = z.object({
  community: z.string(),
  street: z.string(),
  incident_type: z.string(),
  incident_summary: z.string().min(1, 'Summary is required'),
  event_date: z.string(),
  injuries_count: z.string(),
  deaths_count: z.string(),
})

type IncidentFormValues = z.infer<typeof incidentSchema>

// A missing-field path is array-indexed (e.g. `incidents[0].event_date`),
// not row-id keyed, so we only ever want the trailing field name. The one
// exception is `casualties`, a synthetic path with no matching model
// field — it means "injuries or deaths entirely unknown", so tapping it
// should land the officer on injuries_count.
function fieldOfPath(path: string): string {
  const field = path.split('.').pop() ?? path
  return field === 'casualties' ? 'injuries_count' : field
}

// The fields this form exposes, in one list so the seed, the re-sync and the
// save all iterate the same set. Adding an input means adding it here.
const FORM_FIELDS = [
  'community',
  'street',
  'incident_type',
  'incident_summary',
  'event_date',
  'injuries_count',
  'deaths_count',
] as const

// The incident as form values. Also the "seed": the values the form was last
// in sync with the record at, which is what tells an officer's edit apart
// from a field the form simply never revisited.
//
// '' (not 'other') is the seed for "no type yet": 'other' is a real category
// distinct from unknown, so seeding with it would make an untouched null
// field diff against itself on save (null -> 'other'), permanently pinning a
// value the officer never chose.
function incidentToForm(incident: CaptureIncident): IncidentFormValues {
  return {
    community: incident.community ?? '',
    street: incident.street ?? '',
    incident_type: incident.incident_type ?? '',
    incident_summary: incident.incident_summary ?? '',
    event_date: incident.event_date ?? '',
    injuries_count:
      incident.injuries_count != null ? String(incident.injuries_count) : '',
    deaths_count:
      incident.deaths_count != null ? String(incident.deaths_count) : '',
  }
}

// Applies the edited fields on top of the existing incident rather than
// rebuilding the whole record, so fields the form never touches (building
// damage, action taken, relief supplied, ...) survive the edit intact.
//
// `seed` is what makes "edited" mean edited *by the officer*. Writing every
// form value back unconditionally silently reverted anything a chat turn had
// extracted while the form was open -- and worse, diffIncidentPaths then
// reported the reverted value as a manual field, pinning a figure the officer
// never typed. A field still holding its seed is one they left alone, so it
// is not written at all and the record's own value stands.
function applyIncidentForm(
  incident: CaptureIncident,
  form: IncidentFormValues,
  seed: IncidentFormValues,
): CaptureIncident {
  const next: CaptureIncident = { ...incident }
  const edited = (field: (typeof FORM_FIELDS)[number]) =>
    form[field] !== seed[field]

  if (edited('community')) next.community = form.community.trim() || null
  if (edited('street')) next.street = form.street.trim() || null
  if (edited('incident_type'))
    next.incident_type = form.incident_type.trim() || null
  if (edited('incident_summary')) {
    next.incident_summary = form.incident_summary.trim() || null
  }
  if (edited('event_date')) next.event_date = form.event_date.trim() || null
  if (edited('injuries_count')) {
    const injuriesCount = parseOptionalNumber(form.injuries_count)
    next.injuries_count = injuriesCount
    next.injuries_occurred = casualtyOccurred(injuriesCount)
  }
  if (edited('deaths_count')) {
    const deathsCount = parseOptionalNumber(form.deaths_count)
    next.deaths_count = deathsCount
    next.deaths_occurred = casualtyOccurred(deathsCount)
  }
  return next
}

function locationLine(incident: CaptureIncident): string {
  return (
    [
      incident.incident_type ? formatConstant(incident.incident_type) : null,
      incident.community,
      incident.street,
    ]
      .filter(Boolean)
      .join(' · ') || 'Details still needed'
  )
}

function statusLine(incident: CaptureIncident): string | null {
  if (casualtiesUnknown(incident)) return 'Casualties unknown'
  const parts: string[] = []
  if (incident.injuries_count != null || incident.injuries_occurred != null) {
    parts.push(`${incident.injuries_count ?? 0} injured`)
  }
  if (incident.deaths_count != null || incident.deaths_occurred != null) {
    parts.push(`${incident.deaths_count ?? 0} dead`)
  }
  if (incident.relief_supplied === true) parts.push('relief given')
  if (incident.further_assessment_required === true)
    parts.push('assessment needed')
  return parts.length > 0 ? parts.join(' · ') : null
}

// Diffs every field on the incident, not just the ones the form exposes as
// inputs, so a manual path is reported for anything applyIncidentForm
// actually changes -- including derived fields like injuries_occurred that
// the officer never types into directly but that change as a side effect
// of injuries_count. This makes the coverage structural: applyIncidentForm
// builds `next` by spreading `...incident` and overwriting only the fields
// it computes, so every field NOT among those writes is byte-for-byte
// identical to `original` and can never appear here. A field added to
// applyIncidentForm's output is covered automatically, with no separate
// list of "diffable fields" to keep in sync.
function diffIncidentPaths(
  original: CaptureIncident,
  next: CaptureIncident,
): string[] {
  return (Object.keys(original) as (keyof CaptureIncident)[])
    .filter((field) => field !== 'row_id' && original[field] !== next[field])
    .map((field) => incidentPath(original.row_id, field))
}

export function IncidentCard({
  incident,
  missing,
  disabled,
  onEdit,
  onRemove,
}: IncidentCardProps) {
  const [open, setOpen] = useState(false)
  const [focusField, setFocusField] = useState<string | null>(null)

  if (open) {
    return (
      <IncidentEditForm
        incident={incident}
        disabled={disabled}
        focusField={focusField}
        onCancel={() => {
          setOpen(false)
          setFocusField(null)
        }}
        onSave={(next, paths) => {
          if (paths.length > 0) onEdit(next, paths)
          setOpen(false)
          setFocusField(null)
        }}
      />
    )
  }

  const status = statusLine(incident)

  return (
    <div className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {incident.incident_summary || 'Untitled incident'}
          </p>
          <p className="text-muted-foreground">{locationLine(incident)}</p>
          {status ? <p className="text-muted-foreground">{status}</p> : null}
        </div>
        {!disabled ? (
          <div className="flex shrink-0 gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpen(true)}
            >
              Edit
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
              Remove
            </Button>
          </div>
        ) : null}
      </div>
      {missing.length > 0 && !disabled ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {missing.map((item) => (
            <Button
              key={item.path}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setFocusField(fieldOfPath(item.path))
                setOpen(true)
              }}
            >
              {item.message}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function IncidentEditForm({
  incident,
  disabled,
  focusField,
  onCancel,
  onSave,
}: {
  incident: CaptureIncident
  disabled?: boolean
  focusField: string | null
  onCancel: () => void
  onSave: (next: CaptureIncident, paths: string[]) => void
}) {
  // The values the form was last in sync with the record at. TanStack Form
  // snapshots defaultValues at mount and only re-applies them while the whole
  // form is untouched, so the moment the officer types into one field the
  // other six freeze at their mount values -- and a chat turn extracting into
  // any of them is reverted on save. Tracking the seed per field lets each one
  // follow the record independently of what the officer is doing elsewhere.
  const seedRef = useRef(incidentToForm(incident))

  const form = useAppForm({
    defaultValues: seedRef.current,
    validators: { onSubmit: incidentSchema },
    onSubmit: ({ value }) => {
      const next = applyIncidentForm(incident, value, seedRef.current)
      const paths = diffIncidentPaths(incident, next)
      onSave(next, paths)
    },
  })

  useEffect(() => {
    const seed = seedRef.current
    const server = incidentToForm(incident)
    const adopted: Partial<IncidentFormValues> = {}

    for (const field of FORM_FIELDS) {
      // The record did not change this field, so there is nothing to adopt.
      if (server[field] === seed[field]) continue

      const current = form.getFieldValue(field)
      if (current === server[field]) {
        // Already showing it -- form-core re-seeds the whole form while no
        // field is touched, so this is the common path on the first update.
        adopted[field] = server[field]
        continue
      }
      // The officer has this field part-typed. Theirs wins; leaving the seed
      // alone keeps it counting as their edit when they save.
      if (current !== seed[field]) continue

      // Untouched and stale: show what the chat turn extracted.
      form.setFieldValue(field, server[field], { dontUpdateMeta: true })
      adopted[field] = server[field]
    }

    if (Object.keys(adopted).length > 0) {
      seedRef.current = { ...seed, ...adopted }
    }
  }, [incident, form])

  useEffect(() => {
    if (!focusField) return
    document.getElementById(focusField)?.focus()
    // Only run once, on mount: this is a one-shot "land the officer here"
    // action, not a subscription to focusField changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <form
      className="space-y-3 rounded-lg border p-3"
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
    >
      <form.AppForm>
        <div className="grid gap-3 sm:grid-cols-2">
          <form.AppField name="incident_summary">
            {(field) => (
              <field.TextField label="Summary" required disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="incident_type">
            {(field) => (
              <field.SelectField
                label="Type"
                disabled={disabled}
                options={INCIDENT_TYPE_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
            )}
          </form.AppField>
          <form.AppField name="community">
            {(field) => (
              <field.TextField label="Community" disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="street">
            {(field) => <field.TextField label="Street" disabled={disabled} />}
          </form.AppField>
          <form.AppField name="event_date">
            {(field) => (
              <field.TextField label="Date" type="date" disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="injuries_count">
            {(field) => (
              <field.TextField label="Injuries count" disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="deaths_count">
            {(field) => (
              <field.TextField label="Deaths count" disabled={disabled} />
            )}
          </form.AppField>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <form.SubmitButton label="Save" disabled={disabled} />
        </div>
      </form.AppForm>
    </form>
  )
}
