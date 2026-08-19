import { useEffect, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { useAppForm } from '@/hooks/form'
import { incidentPath } from '@/lib/capture-paths'
import {
  INCIDENT_TYPE_OPTIONS,
  casualtyOccurred,
  parseOptionalNumber,
} from '@/lib/capture-mapping'
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

// Applies the edited fields on top of the existing incident rather than
// rebuilding the whole record, so fields the form never touches (building
// damage, action taken, relief supplied, ...) survive the edit intact.
function applyIncidentForm(
  incident: CaptureIncident,
  form: IncidentFormValues,
): CaptureIncident {
  const injuriesCount = parseOptionalNumber(form.injuries_count)
  const deathsCount = parseOptionalNumber(form.deaths_count)
  return {
    ...incident,
    community: form.community.trim() || null,
    street: form.street.trim() || null,
    incident_type: form.incident_type.trim() || null,
    incident_summary: form.incident_summary.trim() || null,
    event_date: form.event_date.trim() || null,
    injuries_occurred: casualtyOccurred(injuriesCount),
    injuries_count: injuriesCount,
    deaths_occurred: casualtyOccurred(deathsCount),
    deaths_count: deathsCount,
  }
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
function diffIncidentPaths(original: CaptureIncident, next: CaptureIncident): string[] {
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

  return (
    <div className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {incident.incident_summary || 'Untitled incident'}
          </p>
          <p className="text-muted-foreground">
            {[
              incident.incident_type ? formatConstant(incident.incident_type) : null,
              incident.community,
              incident.event_date,
            ]
              .filter(Boolean)
              .join(' · ') || 'Details still needed'}
          </p>
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
  const form = useAppForm({
    defaultValues: {
      community: incident.community ?? '',
      street: incident.street ?? '',
      // '' (not 'other') is the seed for "no type yet": 'other' is a real
      // category distinct from unknown, so seeding with it would make an
      // untouched null field diff against itself on save (null -> 'other'),
      // permanently pinning a value the officer never chose.
      incident_type: incident.incident_type ?? '',
      incident_summary: incident.incident_summary ?? '',
      event_date: incident.event_date ?? '',
      injuries_count: incident.injuries_count != null ? String(incident.injuries_count) : '',
      deaths_count: incident.deaths_count != null ? String(incident.deaths_count) : '',
    },
    validators: { onSubmit: incidentSchema },
    onSubmit: ({ value }) => {
      const next = applyIncidentForm(incident, value)
      const paths = diffIncidentPaths(incident, next)
      onSave(next, paths)
    },
  })

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
            {(field) => <field.TextField label="Summary" required disabled={disabled} />}
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
            {(field) => <field.TextField label="Community" disabled={disabled} />}
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
            {(field) => <field.TextField label="Injuries count" disabled={disabled} />}
          </form.AppField>
          <form.AppField name="deaths_count">
            {(field) => <field.TextField label="Deaths count" disabled={disabled} />}
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
