import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useStore } from '@tanstack/react-form'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Label } from '@/components/ui/label'
import { useAppForm } from '@/hooks/form'
import { formatConstant } from '@/lib/format-constant'
import { moduleQueries } from '@/lib/queries/modules'
import { useCreateReport } from '@/lib/queries/reports'
import { templateQueries } from '@/lib/queries/templates'
import {
  buildDataRequirement,
  metricKey,
  selectedMetricKeys,
} from '@/lib/templates'

export const Route = createFileRoute('/reports/new')({
  component: AdminGeneratePage,
})

const adminReportSchema = z.object({
  templateName: z.string().min(1, 'Select a template'),
  params: z.record(z.string(), z.string()),
})

function AdminGeneratePage() {
  const navigate = useNavigate()
  const templatesQuery = useQuery(templateQueries.list())
  const modulesQuery = useQuery(moduleQueries.list())
  const createReport = useCreateReport((id) => {
    void navigate({ to: '/reports/$reportId', params: { reportId: id } })
  })

  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [useDefaultMetrics, setUseDefaultMetrics] = useState(true)

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

      const templateParamNames = template.params.map((param) => param.name)
      const allMetrics =
        modulesQuery.data?.flatMap((module) =>
          module.metrics.map((metric) => ({
            ...metric,
            module: module.name,
          })),
        ) ?? []

      await createReport.mutateAsync({
        template: template.name,
        params: value.params,
        ...(useDefaultMetrics
          ? {}
          : {
              data_requirements: allMetrics
                .filter((metric) =>
                  selectedMetrics.includes(
                    metricKey(metric.module, metric.name),
                  ),
                )
                .map((metric) =>
                  buildDataRequirement(metric, templateParamNames),
                ),
            }),
      })
    },
  })

  const templateName = useStore(form.store, (state) => state.values.templateName)

  const selectedTemplate = useMemo(
    () => templatesQuery.data?.find((template) => template.name === templateName),
    [templateName, templatesQuery.data],
  )

  useEffect(() => {
    if (!templatesQuery.data?.length || templateName) return
    form.setFieldValue('templateName', templatesQuery.data[0].name)
  }, [form, templateName, templatesQuery.data])

  useEffect(() => {
    if (!selectedTemplate) return
    form.setFieldValue(
      'params',
      Object.fromEntries(
        selectedTemplate.params.map((param) => [param.name, '']),
      ),
    )
    setSelectedMetrics(selectedMetricKeys(selectedTemplate.data_requirements))
    setUseDefaultMetrics(true)
  }, [form, selectedTemplate])

  const toggleMetric = (key: string, checked: boolean) => {
    setUseDefaultMetrics(false)
    setSelectedMetrics((current) =>
      checked
        ? [...new Set([...current, key])]
        : current.filter((item) => item !== key),
    )
  }

  const isLoading = templatesQuery.isPending || modulesQuery.isPending
  const isError = templatesQuery.isError || modulesQuery.isError
  const error = templatesQuery.error ?? modulesQuery.error

  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate report (admin)"
        description="Full template picker with dynamic params and optional metric overrides."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" render={<Link to="/reports/corp" />}>
              Corp generate
            </Button>
            <Button variant="outline" render={<Link to="/reports" />}>
              Back to reports
            </Button>
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
                    options={(templatesQuery.data ?? []).map((template) => ({
                      value: template.name,
                      label: `${template.title} (v${template.version})`,
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
                    {(field) => (
                      <field.TextField
                        label={formatConstant(param.name)}
                        required={param.required}
                      />
                    )}
                  </form.AppField>
                ))}
              </div>
            </ContentCard>

            <ContentCard
              title="Metrics"
              description="Defaults to the template's requirements. Uncheck a metric or toggle override to customize."
            >
              <div className="mb-4 flex items-center gap-3">
                <Checkbox
                  checked={useDefaultMetrics}
                  onCheckedChange={(value) =>
                    setUseDefaultMetrics(value === true)
                  }
                />
                <Label>Use template default metrics</Label>
              </div>

              {!useDefaultMetrics ? (
                <div className="space-y-4">
                  {modulesQuery.data?.map((module) => (
                    <div key={module.name} className="space-y-2">
                      <p className="text-sm font-medium">{module.name}</p>
                      <ul className="space-y-2">
                        {module.metrics.map((metric) => {
                          const key = metricKey(module.name, metric.name)
                          const checked = selectedMetrics.includes(key)
                          return (
                            <li key={key} className="flex items-start gap-3">
                              <Checkbox
                                checked={checked}
                                onCheckedChange={(value) =>
                                  toggleMetric(key, value === true)
                                }
                              />
                              <div>
                                <p className="font-mono text-sm">
                                  {metric.name}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                  {metric.description}
                                </p>
                              </div>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {selectedTemplate.data_requirements.map((requirement) => (
                    <li
                      key={`${requirement.module}.${requirement.metric}`}
                      className="font-mono"
                    >
                      {requirement.module}.{requirement.metric}
                    </li>
                  ))}
                </ul>
              )}
            </ContentCard>

            <div className="flex justify-end">
              <form.SubmitButton
                label="Generate report"
                disabled={!useDefaultMetrics && selectedMetrics.length === 0}
              />
            </div>
          </form.AppForm>
        </form>
      ) : null}
    </div>
  )
}
