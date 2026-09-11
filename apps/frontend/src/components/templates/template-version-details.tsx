import { ContentCard } from '@/components/shared/content-card'
import { Badge } from '@/components/ui/badge'
import { formatRequirementLabel } from '@/components/reports/citation-display'
import { formatDisplayLabel, formatDisplayPairs } from '@/lib/format-display'
import { metricKey } from '@/lib/templates'
import { CITATION_RULES, type TemplateInfo } from '@/types/dmcu'

type TemplateVersionDetailsProps = {
  template: TemplateInfo
  readOnly?: boolean
}

export function TemplateVersionDetails({
  template,
  readOnly = false,
}: TemplateVersionDetailsProps) {
  return (
    <div className="space-y-6">
      <ContentCard title="Overview" size="sm">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Name
            </dt>
            <dd className="text-sm">{formatDisplayLabel(template.name)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Version
            </dt>
            <dd className="text-sm">v{template.version}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Description
            </dt>
            <dd className="text-sm">{template.description}</dd>
          </div>
        </dl>
      </ContentCard>

      <ContentCard
        title="Citation rules"
        description="Locked in the engine — always prepended to the system prompt."
      >
        <pre className="whitespace-pre-wrap rounded-md bg-muted/50 p-4 text-sm text-muted-foreground">
          {CITATION_RULES}
        </pre>
      </ContentCard>

      <ContentCard title="Identity">
        <pre className="whitespace-pre-wrap text-sm">
          {template.narration.identity || '(empty)'}
        </pre>
      </ContentCard>

      {template.narration.skills.capture ? (
        <ContentCard title="Capture">
          <pre className="whitespace-pre-wrap text-sm">
            {template.narration.skills.capture}
          </pre>
        </ContentCard>
      ) : null}

      <ContentCard title="Compose">
        <pre className="whitespace-pre-wrap text-sm">
          {template.narration.skills.compose || '(empty)'}
        </pre>
      </ContentCard>

      <ContentCard title="Output sections">
        <div className="flex flex-wrap gap-2">
          {template.narration.output_sections.map((section) => (
            <Badge key={section} variant="outline">
              {formatDisplayLabel(section)}
            </Badge>
          ))}
        </div>
      </ContentCard>

      <ContentCard title="Template params">
        <ul className="space-y-2 text-sm">
          {template.params.map((param) => (
            <li key={param.name} className="flex items-center gap-2">
              <span className="text-sm font-medium">
                {formatDisplayLabel(param.name)}
              </span>
              <Badge variant={param.required ? 'secondary' : 'outline'}>
                {param.required ? 'required' : 'optional'}
              </Badge>
            </li>
          ))}
        </ul>
      </ContentCard>

      <ContentCard
        title="Default metrics"
        description={
          readOnly
            ? 'Metrics assembled into the fact table when no override is supplied at generate time.'
            : undefined
        }
      >
        <ul className="space-y-3 text-sm">
          {template.data_requirements.map((requirement) => (
            <li
              key={metricKey(requirement.module, requirement.metric)}
              className="rounded-md border px-3 py-2"
            >
              <p className="text-sm font-medium">
                {formatRequirementLabel(requirement.module, requirement.metric)}
              </p>
              {Object.keys(requirement.params).length > 0 ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDisplayPairs(requirement.params)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </ContentCard>
    </div>
  )
}
