import type { DataRequirementInfo, MetricSpec, TemplateInfo } from '@/types/dmcu'

export function metricKey(module: string, metric: string) {
  return `${module}.${metric}`
}

export function parseMetricKey(key: string) {
  const [module, ...rest] = key.split('.')
  return { module, metric: rest.join('.') }
}

export function buildRequirementParams(
  metric: MetricSpec,
  templateParamNames: string[],
): Record<string, string> {
  const schemaProps = Object.keys(metric.params_schema?.properties ?? {})
  const params: Record<string, string> = {}

  for (const prop of schemaProps) {
    if (templateParamNames.includes(prop)) {
      params[prop] = `{${prop}}`
    }
  }

  return params
}

export function buildDataRequirement(
  metric: MetricSpec,
  templateParamNames: string[],
): DataRequirementInfo {
  return {
    module: metric.module,
    metric: metric.name,
    params: buildRequirementParams(metric, templateParamNames),
  }
}

/**
 * Strip params the officer left blank before they cross into a query.
 *
 * The generate form seeds every template param to '' when a template is
 * picked, and only the required ones are validated. A blank reaching the
 * backend used to be applied as a real filter (`WHERE community = ''`),
 * matching no row and reporting a confident zero. A blank is an unsupplied
 * param, not an empty-string value, so it is not sent at all.
 */
export function dropBlankParams(
  params: Record<string, string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params)
      .map(([name, value]) => [name, value.trim()] as const)
      .filter(([, trimmed]) => trimmed !== ''),
  )
}

export function selectedMetricKeys(requirements: DataRequirementInfo[]) {
  return requirements.map((req) => metricKey(req.module, req.metric))
}

export function formatRequirementLabel(requirement: DataRequirementInfo) {
  return `${requirement.module}.${requirement.metric}`
}

export function sectionsToText(sections: string[]) {
  return sections.join('\n')
}

export function textToSections(value: string) {
  return value
    .split(/[\n,]+/)
    .map((section) => section.trim())
    .filter(Boolean)
}

export function templateToCreateInput(
  template: TemplateInfo,
  overrides: Partial<TemplateInfo> = {},
): TemplateInfo {
  return {
    ...template,
    ...overrides,
    params: overrides.params ?? template.params,
    data_requirements:
      overrides.data_requirements ?? template.data_requirements,
    narration: overrides.narration ?? template.narration,
  }
}
