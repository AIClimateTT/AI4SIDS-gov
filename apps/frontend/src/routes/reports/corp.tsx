import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'
import { ContentCard } from '@/components/shared/content-card'
import { PageHeader } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { useAppForm } from '@/hooks/form'
import { useCreateReport } from '@/lib/queries/reports'

export const Route = createFileRoute('/reports/corp')({
  component: CorpGeneratePage,
})

const corpReportSchema = z
  .object({
    corporation: z.string().min(1, 'Select your corporation'),
    date_from: z.string().min(1, 'Start date is required'),
    date_to: z.string().min(1, 'End date is required'),
  })
  .refine(
    (values) => !values.date_from || !values.date_to || values.date_from <= values.date_to,
    {
      message: 'End date must be on or after start date',
      path: ['date_to'],
    },
  )

function CorpGeneratePage() {
  const navigate = useNavigate()
  const createReport = useCreateReport((id) => {
    void navigate({ to: '/reports/$reportId', params: { reportId: id } })
  })

  const form = useAppForm({
    defaultValues: {
      corporation: '',
      date_from: '',
      date_to: '',
    },
    validators: {
      onSubmit: corpReportSchema,
    },
    onSubmit: async ({ value }) => {
      await createReport.mutateAsync({
        template: 'single_region_report',
        params: {
          corporation: value.corporation,
          date_from: value.date_from,
          date_to: value.date_to,
        },
      })
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate corp report"
        description="Create a region briefing for your corporation and date range."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" render={<Link to="/" />}>
              Overview
            </Button>
            <Button variant="outline" render={<Link to="/reports" />}>
              All reports
            </Button>
          </div>
        }
      />

      <ContentCard
        title="Report window"
        description="No template selection needed — this always runs the single-region briefing for your corporation."
      >
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void form.handleSubmit()
          }}
        >
          <form.AppForm>
            <form.AppField name="corporation">
              {(field) => (
                <field.SelectField
                  label="Corporation"
                  required
                  placeholder="Select corporation"
                  options={CORPORATION_OPTIONS}
                />
              )}
            </form.AppField>

            <div className="grid gap-4 sm:grid-cols-2">
              <form.AppField name="date_from">
                {(field) => (
                  <field.TextField label="From" type="date" required />
                )}
              </form.AppField>
              <form.AppField name="date_to">
                {(field) => (
                  <field.TextField label="To" type="date" required />
                )}
              </form.AppField>
            </div>

            <div className="flex justify-end pt-2">
              <form.SubmitButton label="Generate report" />
            </div>
          </form.AppForm>
        </form>
      </ContentCard>
    </div>
  )
}
