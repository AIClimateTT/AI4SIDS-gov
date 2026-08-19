import { useEffect, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { ContentCard } from '@/components/shared/content-card'
import { useAppForm } from '@/hooks/form'
import {
  ALERT_LEVELS,
  INCIDENT_TYPE_OPTIONS,
  LOG_CATEGORY_OPTIONS,
  LOG_STATUS_OPTIONS,
  formToCaptureIncident,
  formToCaptureLog,
  nextIncidentRowId,
  toDatetimeLocal,
  toIsoDateTime,
} from '@/lib/capture-mapping'
import { formatConstant } from '@/lib/format-constant'
import type {
  CaptureIncident,
  CaptureLog,
  CaptureSession,
  CaptureSessionUpdate,
} from '@/types/dmcu'

type CapturePaneProps = {
  session: CaptureSession
  disabled?: boolean
  pending?: boolean
  onSave: (payload: CaptureSessionUpdate) => void
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

const logSchema = z.object({
  category: z.string().min(1, 'Select a category'),
  statement: z.string().min(1, 'Statement is required'),
  item: z.string(),
  quantity: z.string(),
  unit: z.string(),
  status: z.string(),
})

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
  }
}

export function CapturePane({ session, disabled, pending, onSave }: CapturePaneProps) {
  const [addingIncident, setAddingIncident] = useState(false)
  const [addingLog, setAddingLog] = useState(false)
  const situationForm = useAppForm({
    defaultValues: {
      as_at: toDatetimeLocal(session.as_at),
      alert_level: session.alert_level,
      present_activity: session.present_activity ?? '',
      situation_overview: session.situation_overview ?? '',
    },
    onSubmit: ({ value }) => {
      onSave(
        payloadOf(session, {
          as_at: toIsoDateTime(value.as_at),
          alert_level: value.alert_level,
          present_activity: value.present_activity,
          situation_overview: value.situation_overview,
        }),
      )
    },
  })

  useEffect(() => {
    situationForm.reset({
      as_at: toDatetimeLocal(session.as_at),
      alert_level: session.alert_level,
      present_activity: session.present_activity ?? '',
      situation_overview: session.situation_overview ?? '',
    })
  }, [session.updated_at])

  const incidentForm = useAppForm({
    defaultValues: {
      community: '',
      street: '',
      incident_type: 'other',
      incident_summary: '',
      event_date: '',
      injuries_count: '',
      deaths_count: '',
    },
    validators: { onSubmit: incidentSchema },
    onSubmit: ({ value }) => {
      const next = formToCaptureIncident(
        value,
        nextIncidentRowId(session.incidents),
      )
      onSave(payloadOf(session, { incidents: [...session.incidents, next] }))
      incidentForm.reset()
      setAddingIncident(false)
    },
  })

  const logForm = useAppForm({
    defaultValues: {
      category: 'other',
      statement: '',
      item: '',
      quantity: '',
      unit: '',
      status: 'none',
    },
    validators: { onSubmit: logSchema },
    onSubmit: ({ value }) => {
      onSave(payloadOf(session, { logs: [...session.logs, formToCaptureLog(value)] }))
      logForm.reset()
      setAddingLog(false)
    },
  })

  return (
    <div className="space-y-4">
      {session.missing.length > 0 ? (
        <ContentCard title="Still needed" size="sm">
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
            {session.missing.map((item) => (
              <li key={item.path}>{item.message}</li>
            ))}
          </ul>
        </ContentCard>
      ) : null}

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          void situationForm.handleSubmit()
        }}
      >
        <situationForm.AppForm>
          <ContentCard
            title="Situation"
            action={
              <situationForm.SubmitButton label="Save" disabled={disabled || pending} />
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <situationForm.AppField name="as_at">
                {(field) => (
                  <field.TextField
                    label="As at"
                    type="datetime-local"
                    disabled={disabled}
                  />
                )}
              </situationForm.AppField>
              <situationForm.AppField name="alert_level">
                {(field) => (
                  <field.SelectField
                    label="Alert level"
                    disabled={disabled}
                    options={ALERT_LEVELS.map((level) => ({
                      value: level,
                      label: formatConstant(level),
                    }))}
                  />
                )}
              </situationForm.AppField>
              <situationForm.AppField name="present_activity">
                {(field) => (
                  <field.TextField label="Present activity" disabled={disabled} />
                )}
              </situationForm.AppField>
            </div>
            <situationForm.AppField name="situation_overview">
              {(field) => (
                <field.TextareaField
                  label="Situation overview"
                  rows={3}
                  disabled={disabled}
                />
              )}
            </situationForm.AppField>
          </ContentCard>
        </situationForm.AppForm>
      </form>

      <ContentCard
        title={`Incidents (${session.incidents.length})`}
        action={
          !disabled ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddingIncident((open) => !open)}
            >
              {addingIncident ? 'Cancel' : 'Add incident'}
            </Button>
          ) : null
        }
      >
        <div className="space-y-3">
          {session.incidents.map((incident) => (
            <IncidentCard
              key={incident.row_id}
              incident={incident}
              disabled={disabled}
              onRemove={() =>
                onSave(
                  payloadOf(session, {
                    incidents: session.incidents.filter(
                      (row) => row.row_id !== incident.row_id,
                    ),
                  }),
                )
              }
            />
          ))}
          {session.incidents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No incidents captured yet.</p>
          ) : null}
          {addingIncident && !disabled ? (
            <form
              className="space-y-3 rounded-lg border p-3"
              onSubmit={(event) => {
                event.preventDefault()
                void incidentForm.handleSubmit()
              }}
            >
              <incidentForm.AppForm>
                <div className="grid gap-3 sm:grid-cols-2">
                  <incidentForm.AppField name="incident_summary">
                    {(field) => <field.TextField label="Summary" required />}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="incident_type">
                    {(field) => (
                      <field.SelectField
                        label="Type"
                        options={INCIDENT_TYPE_OPTIONS.map((option) => ({
                          value: option.value,
                          label: option.label,
                        }))}
                      />
                    )}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="community">
                    {(field) => <field.TextField label="Community" />}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="street">
                    {(field) => <field.TextField label="Street" />}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="event_date">
                    {(field) => <field.TextField label="Date" type="date" />}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="injuries_count">
                    {(field) => <field.TextField label="Injuries count" />}
                  </incidentForm.AppField>
                  <incidentForm.AppField name="deaths_count">
                    {(field) => <field.TextField label="Deaths count" />}
                  </incidentForm.AppField>
                </div>
                <div className="flex justify-end">
                  <incidentForm.SubmitButton label="Add" disabled={pending} />
                </div>
              </incidentForm.AppForm>
            </form>
          ) : null}
        </div>
      </ContentCard>

      <ContentCard
        title={`Situation logs (${session.logs.length})`}
        action={
          !disabled ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddingLog((open) => !open)}
            >
              {addingLog ? 'Cancel' : 'Add log'}
            </Button>
          ) : null
        }
      >
        <div className="space-y-3">
          {session.logs.map((log, index) => (
            <LogCard
              key={`${log.statement}-${index}`}
              log={log}
              disabled={disabled}
              onRemove={() =>
                onSave(
                  payloadOf(session, {
                    logs: session.logs.filter((_, rowIndex) => rowIndex !== index),
                  }),
                )
              }
            />
          ))}
          {session.logs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No situation logs captured yet.</p>
          ) : null}
          {addingLog && !disabled ? (
            <form
              className="space-y-3 rounded-lg border p-3"
              onSubmit={(event) => {
                event.preventDefault()
                void logForm.handleSubmit()
              }}
            >
              <logForm.AppForm>
                <div className="grid gap-3 sm:grid-cols-2">
                  <logForm.AppField name="statement">
                    {(field) => (
                      <field.TextareaField label="Statement" required rows={2} />
                    )}
                  </logForm.AppField>
                  <logForm.AppField name="category">
                    {(field) => (
                      <field.SelectField
                        label="Category"
                        required
                        options={LOG_CATEGORY_OPTIONS.map((option) => ({
                          value: option.value,
                          label: option.label,
                        }))}
                      />
                    )}
                  </logForm.AppField>
                  <logForm.AppField name="item">
                    {(field) => <field.TextField label="Item" />}
                  </logForm.AppField>
                  <logForm.AppField name="quantity">
                    {(field) => <field.TextField label="Quantity" />}
                  </logForm.AppField>
                  <logForm.AppField name="unit">
                    {(field) => <field.TextField label="Unit" />}
                  </logForm.AppField>
                  <logForm.AppField name="status">
                    {(field) => (
                      <field.SelectField
                        label="Status"
                        options={LOG_STATUS_OPTIONS.map((option) => ({
                          value: option.value,
                          label: option.label,
                        }))}
                      />
                    )}
                  </logForm.AppField>
                </div>
                <div className="flex justify-end">
                  <logForm.SubmitButton label="Add" disabled={pending} />
                </div>
              </logForm.AppForm>
            </form>
          ) : null}
        </div>
      </ContentCard>
    </div>
  )
}

function IncidentCard({
  incident,
  disabled,
  onRemove,
}: {
  incident: CaptureIncident
  disabled?: boolean
  onRemove: () => void
}) {
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
          <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
            Remove
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function LogCard({
  log,
  disabled,
  onRemove,
}: {
  log: CaptureLog
  disabled?: boolean
  onRemove: () => void
}) {
  return (
    <div className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">{log.statement}</p>
          <p className="text-muted-foreground">
            {[
              formatConstant(log.category),
              log.quantity != null
                ? `${log.quantity}${log.unit ? ` ${log.unit}` : ''}`
                : null,
              log.status ? formatConstant(log.status) : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        {!disabled ? (
          <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
            Remove
          </Button>
        ) : null}
      </div>
    </div>
  )
}
