import type { TemplateParamInfo } from '@/types/dmcu'

export function paramInputKind(
  param: TemplateParamInfo,
): 'corporation' | 'date' | 'datetime' | 'textarea' | 'text' {
  if (param.multiline) return 'textarea'
  if (param.name === 'corporation') return 'corporation'
  if (param.name === 'date_from' || param.name === 'date_to') return 'date'
  if (param.name === 'as_at') return 'datetime'
  return 'text'
}

export function dropBlankParams(
  params: Record<string, string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params)
      .map(([name, value]) => [name, value.trim()] as const)
      .filter(([, trimmed]) => trimmed !== ''),
  )
}
