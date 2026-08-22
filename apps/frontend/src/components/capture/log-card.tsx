import { useEffect, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { useAppForm } from '@/hooks/form'
import { logPath } from '@/lib/capture-paths'
import { LOG_CATEGORY_OPTIONS, LOG_STATUS_OPTIONS, formToCaptureLog } from '@/lib/capture-mapping'
import { formatConstant } from '@/lib/format-constant'
import type { CaptureLog, CaptureMissingField } from '@/types/dmcu'

export type LogCardProps = {
  log: CaptureLog
  missing: CaptureMissingField[]
  disabled?: boolean
  onEdit: (next: CaptureLog, paths: string[]) => void
  onRemove: () => void
}

const logSchema = z.object({
  category: z.string().min(1, 'Select a category'),
  statement: z.string().min(1, 'Statement is required'),
  item: z.string(),
  quantity: z.string(),
  unit: z.string(),
  status: z.string(),
})

type LogFormValues = z.infer<typeof logSchema>

// formToCaptureLog covers every field CaptureLog has, so unlike incidents
// there is no risk of it silently wiping fields the form never shows.
const LOG_FORM_FIELDS = [
  'category',
  'statement',
  'item',
  'quantity',
  'unit',
  'status',
] as const satisfies readonly (keyof CaptureLog)[]

function logLead(log: CaptureLog): string | null {
  const item = log.item?.trim() || null
  const quantity =
    log.quantity != null ? `${log.quantity}${item ? ` ${item}` : log.unit ? ` ${log.unit}` : ''}` : item
  if (!quantity) return null
  return log.status ? `${quantity} · ${formatConstant(log.status)}` : quantity
}

function fieldOfPath(path: string): string {
  return path.split('.').pop() ?? path
}

function diffLogPaths(original: CaptureLog, next: CaptureLog): string[] {
  return LOG_FORM_FIELDS.filter((field) => original[field] !== next[field]).map((field) =>
    logPath(original.row_id, field),
  )
}

export function LogCard({ log, missing, disabled, onEdit, onRemove }: LogCardProps) {
  const [open, setOpen] = useState(false)
  const [focusField, setFocusField] = useState<string | null>(null)

  if (open) {
    return (
      <LogEditForm
        log={log}
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

  const lead = logLead(log)

  return (
    <div className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          {lead ? (
            <>
              <p className="font-medium">{lead}</p>
              <p className="text-muted-foreground">{log.statement}</p>
            </>
          ) : (
            <>
              <p className="font-medium">{log.statement}</p>
              <p className="text-muted-foreground">{formatConstant(log.category)}</p>
            </>
          )}
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

function LogEditForm({
  log,
  disabled,
  focusField,
  onCancel,
  onSave,
}: {
  log: CaptureLog
  disabled?: boolean
  focusField: string | null
  onCancel: () => void
  onSave: (next: CaptureLog, paths: string[]) => void
}) {
  const form = useAppForm({
    defaultValues: {
      category: log.category ?? 'other',
      statement: log.statement ?? '',
      item: log.item ?? '',
      quantity: log.quantity != null ? String(log.quantity) : '',
      unit: log.unit ?? '',
      status: log.status ?? 'none',
    },
    validators: { onSubmit: logSchema },
    onSubmit: ({ value }) => {
      const next = formToCaptureLog(value as LogFormValues, log.row_id)
      const paths = diffLogPaths(log, next)
      onSave(next, paths)
    },
  })

  useEffect(() => {
    if (!focusField) return
    document.getElementById(focusField)?.focus()
    // One-shot "land the officer here" action on open, not a subscription.
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
          <form.AppField name="statement">
            {(field) => (
              <field.TextareaField label="Statement" required rows={2} disabled={disabled} />
            )}
          </form.AppField>
          <form.AppField name="category">
            {(field) => (
              <field.SelectField
                label="Category"
                required
                disabled={disabled}
                options={LOG_CATEGORY_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
            )}
          </form.AppField>
          <form.AppField name="item">
            {(field) => <field.TextField label="Item" disabled={disabled} />}
          </form.AppField>
          <form.AppField name="quantity">
            {(field) => <field.TextField label="Quantity" disabled={disabled} />}
          </form.AppField>
          <form.AppField name="unit">
            {(field) => <field.TextField label="Unit" disabled={disabled} />}
          </form.AppField>
          <form.AppField name="status">
            {(field) => (
              <field.SelectField
                label="Status"
                disabled={disabled}
                options={LOG_STATUS_OPTIONS.map((option) => ({
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
