import { useEffect, useRef, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { useAppForm } from '@/hooks/form'
import { incidentPath } from '@/lib/capture-paths'
import {
  INCIDENT_SCOPE_OPTIONS,
  INCIDENT_TYPE_OPTIONS,
  YES_NO_OPTIONS,
  casualtyOccurred,
  formToYesNo,
  parseOptionalNumber,
  yesNoToForm,
} from '@/lib/capture-mapping'
import { casualtiesUnknown } from '@/lib/capture-tallies'
import { formatConstant } from '@/lib/format-constant'
import type { CaptureIncident, CaptureMissingField, IncidentScope } from '@/types/dmcu'

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
  incident_scope: z.string(),
  house_number: z.string(),
  households_affected: z.string(),
  persons_affected: z.string(),
  persons_displaced: z.string(),
  persons_marooned: z.string(),
  access_blocked: z.string(),
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
  'incident_scope',
  'house_number',
  'households_affected',
  'persons_affected',
  'persons_displaced',
  'persons_marooned',
  'access_blocked',
] as const

const COUNT_FIELDS = [
  'households_affected',
  'persons_affected',
  'persons_displaced',
  'persons_marooned',
] as const

function countToForm(value: number | null | undefined): string {
  return value != null ? String(value) : ''
}

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
    incident_scope: incident.incident_scope ?? '',
    house_number: incident.house_number ?? '',
    households_affected: countToForm(incident.households_affected),
    persons_affected: countToForm(incident.persons_affected),
    persons_displaced: countToForm(incident.persons_displaced),
    persons_marooned: countToForm(incident.persons_marooned),
    access_blocked: yesNoToForm(incident.access_blocked),
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
  if (edited('incident_scope')) {
    next.incident_scope = (form.incident_scope || null) as IncidentScope | null
  }
  if (edited('house_number')) next.house_number = form.house_number.trim() || null
  for (const field of COUNT_FIELDS) {
    if (edited(field)) next[field] = parseOptionalNumber(form[field])
  }
  if (edited('access_blocked')) next.access_blocked = formToYesNo(form.access_blocked)
  return next
}

function locationLine(incident: CaptureIncident): string {
  return (
    [
      incident.incident_type ? formatConstant(incident.incident_type) : null,
      incident.incident_scope === 'household' ? 'Household' : null,
      incident.community,
      [incident.house_number, incident.street].filter(Boolean).join(' ') || null,
    ]
      .filter(Boolean)
      .join(' · ') || 'Details still needed'
  )
}

function statusLine(incident: CaptureIncident): string | null {
  const parts: string[] = []
  if (incident.households_affected != null)
    parts.push(`${incident.households_affected} households`)
  if (incident.persons_affected != null)
    parts.push(`${incident.persons_affected} persons affected`)
  if (incident.persons_displaced != null)
    parts.push(`${incident.persons_displaced} displaced`)
  if (incident.persons_marooned != null)
    parts.push(`${incident.persons_marooned} marooned`)
  if (incident.access_blocked === true) parts.push('access blocked')
  if (casualtiesUnknown(incident)) {
    parts.push('Casualties unknown')
    return parts.join(' · ')
  }
  // "No injuries" without a figure is not a count of zero.
  if (incident.injuries_count != null) {
    parts.push(`${incident.injuries_count} injured`)
  } else if (incident.injuries_occurred === false) {
    parts.push('no injuries reported')
  } else if (incident.injuries_occurred === true) {
    parts.push('injuries, number unknown')
  }
  if (incident.deaths_count != null) {
    parts.push(`${incident.deaths_count} dead`)
  } else if (incident.deaths_occurred === false) {
    parts.push('no deaths reported')
  } else if (incident.deaths_occurred === true) {
    parts.push('deaths, number unknown')
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
  // Union of both key sets: a record saved before a field existed has no key
  // for it, and a value typed into that field must still count as an edit.
  const fields = new Set([...Object.keys(original), ...Object.keys(next)])
  return ([...fields] as (keyof CaptureIncident)[])
    .filter(
      (field) =>
        field !== 'row_id' && (original[field] ?? null) !== (next[field] ?? null),
    )
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
          <form.AppField name="incident_scope">
            {(field) => (
              <field.SelectField
                label="Kind"
                placeholder="Not set"
                disabled={disabled}
                options={INCIDENT_SCOPE_OPTIONS.map((option) => ({
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
            {(field) => (
              <field.TextField
                label="Street"
                helpText="For an area, list the streets separated by commas"
                disabled={disabled}
              />
            )}
          </form.AppField>
          <form.AppField name="house_number">
            {(field) => (
              <field.TextField
                label="House number or LP"
                helpText="Household incidents only"
                disabled={disabled}
              />
            )}
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
          <form.AppField name="households_affected">
            {(field) => (
              <field.TextField label="Households affected" disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="persons_affected">
            {(field) => (
              <field.TextField label="Persons affected" disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="persons_displaced">
            {(field) => (
              <field.TextField
                label="Persons displaced"
                helpText="Evacuated or in a shelter"
                disabled={disabled}
              />
            )}
          </form.AppField>
          <form.AppField name="persons_marooned">
            {(field) => (
              <field.TextField
                label="Persons marooned"
                helpText="Stranded or cut off by water"
                disabled={disabled}
              />
            )}
          </form.AppField>
          <form.AppField name="access_blocked">
            {(field) => (
              <field.SelectField
                label="Road or access blocked"
                placeholder="Not known"
                disabled={disabled}
                options={YES_NO_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
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
