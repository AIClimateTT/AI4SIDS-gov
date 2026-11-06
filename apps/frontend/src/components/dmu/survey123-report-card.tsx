import { useNavigate } from '@tanstack/react-router'

import { ContentCard } from '@/components/shared/content-card'
import { useAppForm } from '@/hooks/form'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { useCreateReport } from '@/lib/queries/reports'

function isoDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function Survey123ReportCard({ today = new Date() }: { today?: Date }) {
  const navigate = useNavigate()
  const createReport = useCreateReport((id) => {
    void navigate({ to: '/dmu/reports/$reportId', params: { reportId: id } })
  })

  const form = useAppForm({
    defaultValues: {
      date_from: `${today.getFullYear()}-01-01`,
      date_to: isoDay(today),
      corporation: '',
    },
    onSubmit: async ({ value }) => {
      await createReport.mutateAsync({
        template: 'survey123_summary',
        params: {
          date_from: value.date_from,
          date_to: value.date_to,
          ...(value.corporation ? { corporation: value.corporation } : {}),
        },
      })
    },
  })

  return (
    <ContentCard
      title="Generate report"
      description="A short report on the verified Survey123 records uploaded for this period."
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.AppForm>
          <div className="grid gap-4 sm:grid-cols-3">
            <form.AppField name="date_from">
              {(field) => (
                <field.TextField label="Date from" type="date" required />
              )}
            </form.AppField>
            <form.AppField name="date_to">
              {(field) => (
                <field.TextField label="Date to" type="date" required />
              )}
            </form.AppField>
            <form.AppField name="corporation">
              {(field) => (
                <field.SelectField
                  label="Corporation (optional)"
                  options={CORPORATION_OPTIONS}
                />
              )}
            </form.AppField>
          </div>
          <div className="flex justify-end">
            <form.SubmitButton label="Generate report" />
          </div>
        </form.AppForm>
      </form>
    </ContentCard>
  )
}
