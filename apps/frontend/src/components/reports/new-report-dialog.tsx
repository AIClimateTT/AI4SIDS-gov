import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { AppDialog } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { useAppForm } from '@/hooks/form'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { useCreateReport } from '@/lib/queries/reports'
import { dropBlankParams } from '@/lib/templates'

export type NewReportKind = 'minister' | 'survey123'

const HAZARD_OPTIONS = [
  'Adverse weather',
  'Flood',
  'Landslide',
  'High wind',
  'Fire',
  'Other',
].map((label) => ({ value: label, label }))

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function isoDay(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function localDateTime(date: Date): string {
  return `${isoDay(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function NewReportDialog({
  open,
  onOpenChange,
  initialKind = 'minister',
  today = new Date(),
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialKind?: NewReportKind
  today?: Date
}) {
  const navigate = useNavigate()
  const createReport = useCreateReport((id) => {
    void navigate({ to: '/dmu/reports/$reportId', params: { reportId: id } })
  })
  const [kind, setKind] = useState<NewReportKind>(initialKind)
  const [step, setStep] = useState<'dates' | 'ministry'>('dates')
  const [dateError, setDateError] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)

  const form = useAppForm({
    defaultValues: {
      date_from: `${today.getFullYear()}-01-01`,
      date_to: isoDay(today),
      corporation: '',
      as_at: localDateTime(today),
      hazard: 'Adverse weather',
      present_activity: '',
      alert_level: '',
      situation_overview: '',
      ministry_response: '',
    },
    onSubmit: async ({ value }) => {
      setFailure(null)
      const params: Record<string, string> =
        kind === 'survey123'
          ? {
              date_from: value.date_from,
              date_to: value.date_to,
              corporation: value.corporation,
            }
          : {
              date_from: value.date_from,
              date_to: value.date_to,
              as_at: value.as_at,
              hazard: value.hazard,
              present_activity: value.present_activity,
              alert_level: value.alert_level,
              situation_overview: value.situation_overview,
              ministry_response: value.ministry_response,
            }
      try {
        await createReport.mutateAsync({
          template: kind === 'survey123' ? 'survey123_summary' : 'minister_situation_report',
          params: dropBlankParams(params),
        })
      } catch (error) {
        setFailure(error instanceof Error ? error.message : 'The report could not be generated.')
      }
    },
  })

  function datesAreValid(): boolean {
    const { date_from, date_to } = form.state.values
    if (!date_from || !date_to) {
      setDateError('Choose a start and end date.')
      return false
    }
    if (date_from > date_to) {
      setDateError('The start date is after the end date.')
      return false
    }
    setDateError(null)
    return true
  }

  const onMinisterSections = kind === 'minister' && step === 'ministry'

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title="New report"
      description={
        kind === 'survey123'
          ? 'A short report on the verified Survey123 records for this period.'
          : "Built from each corporation's latest filing in the period."
      }
      className="sm:max-w-xl"
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (kind === 'minister' && step === 'dates') {
            if (datesAreValid()) setStep('ministry')
            return
          }
          if (datesAreValid()) void form.handleSubmit()
        }}
      >
        <form.AppForm>
          {!onMinisterSections ? (
            <>
              <div className="flex gap-2">
                {(
                  [
                    ['minister', 'Minister report'],
                    ['survey123', 'Survey123 summary'],
                  ] as const
                ).map(([value, label]) => (
                  <Button
                    key={value}
                    type="button"
                    size="sm"
                    variant={kind === value ? 'default' : 'outline'}
                    onClick={() => setKind(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <form.AppField name="date_from">
                  {(field) => <field.TextField label="Date from" type="date" required />}
                </form.AppField>
                <form.AppField name="date_to">
                  {(field) => <field.TextField label="Date to" type="date" required />}
                </form.AppField>
              </div>
              {kind === 'survey123' ? (
                <form.AppField name="corporation">
                  {(field) => (
                    <field.SelectField
                      label="Corporation (optional)"
                      options={CORPORATION_OPTIONS}
                    />
                  )}
                </form.AppField>
              ) : null}
            </>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <form.AppField name="as_at">
                  {(field) => <field.TextField label="As at" type="datetime-local" />}
                </form.AppField>
                <form.AppField name="hazard">
                  {(field) => <field.SelectField label="Hazard" options={HAZARD_OPTIONS} />}
                </form.AppField>
                <form.AppField name="present_activity">
                  {(field) => <field.TextField label="Present activity" />}
                </form.AppField>
                <form.AppField name="alert_level">
                  {(field) => <field.TextField label="Alert wording" />}
                </form.AppField>
              </div>
              <form.AppField name="situation_overview">
                {(field) => <field.TextareaField label="Situation overview (optional)" />}
              </form.AppField>
              <form.AppField name="ministry_response">
                {(field) => <field.TextareaField label="Ministry response (optional)" />}
              </form.AppField>
            </>
          )}

          {dateError ? <p className="text-sm text-destructive">{dateError}</p> : null}
          {failure ? <p className="text-sm text-destructive">{failure}</p> : null}

          <div className="flex justify-end gap-2">
            {onMinisterSections ? (
              <Button type="button" variant="outline" onClick={() => setStep('dates')}>
                Back
              </Button>
            ) : null}
            {kind === 'minister' && step === 'dates' ? (
              <Button type="submit">Next</Button>
            ) : (
              <form.SubmitButton label="Generate report" />
            )}
          </div>
        </form.AppForm>
      </form>
    </AppDialog>
  )
}
