import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useStore } from '@tanstack/react-form'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'
import { z } from 'zod'

import {
  ButtonLink,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { useAppForm } from '@/hooks/form'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { formatDisplayLabel } from '@/lib/format-display'
import { useCreateReport } from '@/lib/queries/reports'
import { templateQueries } from '@/lib/queries/templates'
import { dropBlankParams, paramInputKind } from '@/lib/templates'

export const Route = createFileRoute('/dmu/reports/new')({
  component: AdminGeneratePage,
})

const adminReportSchema = z.object({
  templateName: z.string().min(1, 'Select a template'),
  params: z.record(z.string(), z.string()),
})

function AdminGeneratePage() {
  const navigate = useNavigate()
  const templatesQuery = useQuery(templateQueries.list())
  const createReport = useCreateReport((id) => {
    void navigate({ to: '/dmu/reports/$reportId', params: { reportId: id } })
  })

  const form = useAppForm({
    defaultValues: {
      templateName: '',
      params: {} as Record<string, string>,
    },
    validators: {
      onSubmit: adminReportSchema,
    },
    onSubmit: async ({ value }) => {
      const template = templatesQuery.data?.find(
        (item) => item.name === value.templateName,
      )
      if (!template) return

      const missing = template.params.filter(
        (param) => param.required && !value.params[param.name]?.trim(),
      )
      if (missing.length > 0) {
        throw new Error(
          `Missing required params: ${missing.map((p) => p.name).join(', ')}`,
        )
      }

      // Every template param is seeded to '' when a template is picked, so an
      // untouched optional field would POST as a blank. The backend now treats
      // a blank as absent too, but sending one at all describes a filter the
      // officer never asked for.
      const params = dropBlankParams(value.params)

      await createReport.mutateAsync({
        template: template.name,
        params,
      })
    },
  })

  const generateTemplates = useMemo(
    () =>
      (templatesQuery.data ?? []).filter(
        (template) => template.name === 'minister_situation_report',
      ),
    [templatesQuery.data],
  )

  const templateName = useStore(form.store, (state) => state.values.templateName)

  const selectedTemplate = useMemo(
    () => generateTemplates.find((template) => template.name === templateName),
    [generateTemplates, templateName],
  )

  useEffect(() => {
    if (!generateTemplates.length || templateName) return
    form.setFieldValue('templateName', generateTemplates[0].name)
  }, [form, generateTemplates, templateName])

  useEffect(() => {
    if (!selectedTemplate) return
    form.setFieldValue(
      'params',
      Object.fromEntries(
        selectedTemplate.params.map((param) => [param.name, '']),
      ),
    )
  }, [form, selectedTemplate])

  const isLoading = templatesQuery.isPending
  const isError = templatesQuery.isError
  const error = templatesQuery.error

  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate report"
        description="Built from each corporation's latest filing in the period."
        actions={
          <div className="flex flex-wrap gap-2">
            <ButtonLink variant="outline" to="/dmu/reports">
              Back to reports
            </ButtonLink>
          </div>
        }
      />

      {isLoading ? <LoadingBlock rows={6} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load generate form"
          description={error?.message ?? 'Unknown error'}
        />
      ) : null}

      {selectedTemplate ? (
        <form
          className="space-y-6"
          onSubmit={(event) => {
            event.preventDefault()
            void form.handleSubmit()
          }}
        >
          <form.AppForm>
            <ContentCard title="Template">
              <form.AppField name="templateName">
                {(field) => (
                  <field.SelectField
                    label="Template"
                    required
                    options={generateTemplates.map((template) => ({
                      value: template.name,
                      label: template.title,
                    }))}
                  />
                )}
              </form.AppField>
            </ContentCard>

            <ContentCard title="Parameters">
              <div className="grid gap-4 sm:grid-cols-2">
                {selectedTemplate.params.map((param) => (
                  <form.AppField
                    key={param.name}
                    name={`params.${param.name}`}
                  >
                    {(field) => {
                      const label = formatDisplayLabel(param.name)
                      switch (paramInputKind(param)) {
                        case 'corporation':
                          return (
                            <field.SelectField
                              label={label}
                              required={param.required}
                              options={CORPORATION_OPTIONS}
                            />
                          )
                        case 'date':
                          return (
                            <field.TextField
                              label={label}
                              type="date"
                              required={param.required}
                            />
                          )
                        case 'datetime':
                          return (
                            <field.TextField
                              label={label}
                              type="datetime-local"
                              required={param.required}
                            />
                          )
                        case 'textarea':
                          return (
                            <div className="sm:col-span-2">
                              <field.TextareaField
                                label={label}
                                required={param.required}
                              />
                            </div>
                          )
                        default:
                          return (
                            <field.TextField
                              label={label}
                              required={param.required}
                            />
                          )
                      }
                    }}
                  </form.AppField>
                ))}
              </div>
            </ContentCard>

            <div className="flex justify-end">
              <form.SubmitButton label="Generate report" />
            </div>
          </form.AppForm>
        </form>
      ) : null}
    </div>
  )
}
