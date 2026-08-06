import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { CsvTemplateLinks } from '@/components/submissions/csv-template-links'
import { SubmissionResult } from '@/components/submissions/submission-result'
import { useAppForm } from '@/hooks/form'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import { formatConstant } from '@/lib/format-constant'
import { submissionQueries, useFileSubmission } from '@/lib/queries/submissions'
import type { SubmissionIngestResult } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

// Mirrors the backend's ALERT_LEVELS tuple in app/modules/sitreps/models.py.
const ALERT_LEVELS = [
  'green',
  'yellow',
  'orange',
  'red',
  'discontinued',
  'none',
] as const

const fileSubmissionSchema = z.object({
  as_at: z.string().min(1, 'As at is required'),
  alert_level: z.string().min(1, 'Select an alert level'),
  present_activity: z.string(),
  situation_overview: z.string(),
  // z.instanceof(File).optional() makes the *key* optional, but useAppForm's
  // defaultValues always includes these keys (possibly undefined) — a union
  // with z.undefined() keeps the key required while still allowing no file.
  incidentsFile: z.union([z.instanceof(File), z.undefined()]),
  logsFile: z.union([z.instanceof(File), z.undefined()]),
})

function nowDatetimeLocal(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(
    now.getHours(),
  )}:${pad(now.getMinutes())}`
}

export const Route = createFileRoute('/corp/events/$eventId/file')({
  component: FileSubmissionPage,
})

function FileSubmissionPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to file a situation report." />
    )
  }

  return <FileSubmissionForm identity={identity} />
}

function FileSubmissionForm({ identity }: { identity: CorpIdentity }) {
  const { eventId } = Route.useParams()
  const eventIdNum = Number(eventId)
  const [result, setResult] = useState<SubmissionIngestResult | null>(null)

  const submissionsQuery = useQuery(
    submissionQueries.list({ event_id: eventIdNum }),
  )
  const latestId = submissionsQuery.data?.[0]?.id
  const latestDetailQuery = useQuery(submissionQueries.detail(latestId ?? 0))
  const latest = latestDetailQuery.data

  const fileSubmission = useFileSubmission()

  const form = useAppForm({
    defaultValues: {
      as_at: nowDatetimeLocal(),
      alert_level: 'none',
      present_activity: '',
      situation_overview: '',
      incidentsFile: undefined as File | undefined,
      logsFile: undefined as File | undefined,
    },
    validators: {
      onSubmit: fileSubmissionSchema,
    },
    onSubmit: async ({ value }) => {
      const submitted = await fileSubmission.mutateAsync({
        corporation: identity.corporation,
        as_at: value.as_at,
        event_id: eventIdNum,
        alert_level: value.alert_level,
        present_activity: value.present_activity || undefined,
        situation_overview: value.situation_overview || undefined,
        incidentsFile: value.incidentsFile,
        logsFile: value.logsFile,
      })
      setResult(submitted)
    },
  })

  // A follow-up filing is usually an edit, not a blank form — pre-fill from
  // the most recent submission once, so later user edits aren't clobbered if
  // this query refetches.
  const prefilled = useRef(false)
  useEffect(() => {
    if (!latest || prefilled.current) return
    form.setFieldValue('alert_level', latest.alert_level)
    form.setFieldValue('present_activity', latest.present_activity ?? '')
    form.setFieldValue('situation_overview', latest.situation_overview ?? '')
    prefilled.current = true
  }, [form, latest])

  if (result) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={`Situation Report #${result.sequence_no} filed`}
          description="Here is exactly what landed and what was rejected."
          actions={
            <Button
              variant="outline"
              render={
                <Link to="/corp/events/$eventId" params={{ eventId }} />
              }
            >
              Back to event
            </Button>
          }
        />
        <ContentCard title="Filing result">
          <SubmissionResult result={result} />
        </ContentCard>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="File a situation report"
        description="Fill in what changed since the last filing."
        actions={
          <Button
            variant="outline"
            render={<Link to="/corp/events/$eventId" params={{ eventId }} />}
          >
            Back to event
          </Button>
        }
      />

      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.AppForm>
          <ContentCard title="Situation">
            <div className="grid gap-4 sm:grid-cols-2">
              <form.AppField name="as_at">
                {(field) => (
                  <field.TextField label="As at" type="datetime-local" required />
                )}
              </form.AppField>
              <form.AppField name="alert_level">
                {(field) => (
                  <field.SelectField
                    label="Alert level"
                    required
                    options={ALERT_LEVELS.map((level) => ({
                      value: level,
                      label: formatConstant(level),
                    }))}
                  />
                )}
              </form.AppField>
              <form.AppField name="present_activity">
                {(field) => <field.TextField label="Present activity" />}
              </form.AppField>
            </div>
            <form.AppField name="situation_overview">
              {(field) => (
                <field.TextareaField label="Situation overview" rows={5} />
              )}
            </form.AppField>
          </ContentCard>

          <ContentCard title="Spreadsheets">
            <CsvTemplateLinks />
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <form.AppField name="incidentsFile">
                {(field) => <field.FileField label="Incidents file" accept=".csv" />}
              </form.AppField>
              <form.AppField name="logsFile">
                {(field) => (
                  <field.FileField label="Situation logs file" accept=".csv" />
                )}
              </form.AppField>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Uploading no files is a valid filing — use it to record "no
              reports at this time."
            </p>
          </ContentCard>

          <div className="flex justify-end">
            <form.SubmitButton label="File report" />
          </div>
        </form.AppForm>
      </form>
    </div>
  )
}
