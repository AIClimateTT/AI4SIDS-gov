import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ButtonLink, EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { moduleQueries } from '@/lib/queries/modules'
import {
  templateQueries,
  useCreateTemplateVersion,
} from '@/lib/queries/templates'
import {
  buildDataRequirement,
  metricKey,
  sectionsToText,
  selectedMetricKeys,
  textToSections,
} from '@/lib/templates'
import { CITATION_RULES } from '@/types/dmcu'

export const Route = createFileRoute('/dmu/admin/templates/$name/new')({
  component: NewTemplateVersionPage,
})

function NewTemplateVersionPage() {
  const { name } = Route.useParams()
  const navigate = useNavigate()
  const latestQuery = useQuery(templateQueries.list())
  const modulesQuery = useQuery(moduleQueries.list())

  const latest = useMemo(
    () => latestQuery.data?.find((template) => template.name === name),
    [latestQuery.data, name],
  )

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [identity, setIdentity] = useState('')
  const [capturePrompt, setCapturePrompt] = useState('')
  const [composePrompt, setComposePrompt] = useState('')
  const [outputSectionsText, setOutputSectionsText] = useState('')
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (!latest || initialized) return
    setTitle(latest.title)
    setDescription(latest.description)
    setIdentity(latest.narration.identity)
    setCapturePrompt(latest.narration.skills.capture ?? '')
    setComposePrompt(latest.narration.skills.compose)
    setOutputSectionsText(sectionsToText(latest.narration.output_sections))
    setSelectedMetrics(selectedMetricKeys(latest.data_requirements))
    setInitialized(true)
  }, [initialized, latest])

  const createVersion = useCreateTemplateVersion((created) => {
    void navigate({
      to: '/dmu/admin/templates/$name/versions/$version',
      params: { name: created.name, version: String(created.version) },
    })
  })

  const templateParamNames = latest?.params.map((param) => param.name) ?? []
  const allMetrics =
    modulesQuery.data?.flatMap((module) =>
      module.metrics.map((metric) => ({
        ...metric,
        module: module.name,
      })),
    ) ?? []

  const toggleMetric = (key: string, checked: boolean) => {
    setSelectedMetrics((current) =>
      checked ? [...new Set([...current, key])] : current.filter((item) => item !== key),
    )
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!latest) return

    const dataRequirements = allMetrics
      .filter((metric) => selectedMetrics.includes(metricKey(metric.module, metric.name)))
      .map((metric) => buildDataRequirement(metric, templateParamNames))

    createVersion.mutate({
      name,
      title,
      description,
      params: latest.params,
      data_requirements: dataRequirements,
      narration: {
        identity,
        skills: {
          capture: capturePrompt,
          compose: composePrompt,
        },
        output_sections: textToSections(outputSectionsText),
      },
    })
  }

  const isLoading = latestQuery.isPending || modulesQuery.isPending
  const isError = latestQuery.isError || modulesQuery.isError
  const error = latestQuery.error ?? modulesQuery.error

  return (
    <div className="space-y-6">
      <PageHeader
        title={`New version · ${name}`}
        description="Creates an immutable template version. Citation rules stay locked in the engine."
        actions={
          <ButtonLink
            variant="outline"
            to="/dmu/admin/templates/$name"
            params={{ name }}
          >
            Cancel
          </ButtonLink>
        }
      />

      {isLoading ? <LoadingBlock rows={6} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load editor data"
          description={error?.message ?? 'Unknown error'}
        />
      ) : null}

      {latest ? (
        <form className="space-y-6" onSubmit={handleSubmit}>
          <ContentCard title="Basics">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  required
                />
              </div>
            </div>
          </ContentCard>

          <ContentCard
            title="Citation rules (read-only)"
            description="These rules are always prepended by the engine and cannot be removed."
          >
            <pre className="whitespace-pre-wrap rounded-md bg-muted/50 p-4 text-sm text-muted-foreground">
              {CITATION_RULES}
            </pre>
          </ContentCard>

          <ContentCard title="Identity">
            <div className="space-y-2">
              <Label htmlFor="identity">Who this agent is</Label>
              <Textarea
                id="identity"
                value={identity}
                onChange={(event) => setIdentity(event.target.value)}
                rows={6}
                required
              />
            </div>
          </ContentCard>

          {capturePrompt || name === 'corp_situation_report' ? (
            <ContentCard title="Capture">
              <div className="space-y-2">
                <Label htmlFor="capture-skill">Capture skill</Label>
                <Textarea
                  id="capture-skill"
                  value={capturePrompt}
                  onChange={(event) => setCapturePrompt(event.target.value)}
                  rows={8}
                />
              </div>
            </ContentCard>
          ) : null}

          <ContentCard title="Compose">
            <div className="space-y-2">
              <Label htmlFor="compose-skill">Compose skill</Label>
              <Textarea
                id="compose-skill"
                value={composePrompt}
                onChange={(event) => setComposePrompt(event.target.value)}
                rows={8}
                required
              />
            </div>
          </ContentCard>

          <ContentCard
            title="Output sections"
            description="One section id per line."
          >
            <Textarea
              value={outputSectionsText}
              onChange={(event) => setOutputSectionsText(event.target.value)}
              rows={5}
              placeholder="situation_overview"
            />
          </ContentCard>

          <ContentCard
            title="Default metrics"
            description="Select at least one metric. Param bindings use template params automatically."
          >
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
                            <p className="font-mono text-sm">{metric.name}</p>
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
          </ContentCard>

          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={
                createVersion.isPending ||
                selectedMetrics.length === 0 ||
                textToSections(outputSectionsText).length === 0
              }
            >
              {createVersion.isPending ? 'Creating…' : 'Create version'}
            </Button>
          </div>
        </form>
      ) : null}

      {!isLoading && !latest ? (
        <EmptyState
          title="Template not found"
          description={`No latest version exists for ${name}.`}
        />
      ) : null}
    </div>
  )
}
