import type {
  DataRequirementInfo,
  MetricSpec,
  TemplateParamInfo,
} from '@/types/dmcu'
import { formatDisplayLabel } from '@/lib/format-display'

export function paramInputKind(
  param: TemplateParamInfo,
): 'corporation' | 'date' | 'datetime' | 'textarea' | 'text' {
  if (param.multiline) return 'textarea'
  if (param.name === 'corporation') return 'corporation'
  if (param.name === 'date_from' || param.name === 'date_to') return 'date'
  if (param.name === 'as_at') return 'datetime'
  return 'text'
}

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
  return `${formatDisplayLabel(requirement.module)} · ${formatDisplayLabel(requirement.metric)}`
}
