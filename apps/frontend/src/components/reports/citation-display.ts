import { sourceLabel } from '@/components/shared/source-badge'
import { formatDisplayLabel, formatDisplayValue } from '@/lib/format-display'
import type { Fact } from '@/types/dmcu'

/** Reader-facing name for citation.query_ref. The JSON field does not change. */
export const SOURCE_QUERY_LABEL = 'Source query'

/** Reader-facing name for citation.as_of. The JSON field does not change. */
export const AS_OF_LABEL = 'As of'

export function formatFactValue(fact: Pick<Fact, 'value' | 'unit'>): string {
  const unit = fact.unit ? ` ${fact.unit}` : ''
  return `${fact.value}${unit}`
}

export function formatMetricLabel(metric: string): string {
  return formatDisplayLabel(metric)
}

/**
 * Values stored as slugs or snake_case constants, shown to a reader.
 * Corporation ids become the corporation's name; other snake_case becomes
 * Title Case; dates and free text pass through.
 */
export function humanizeStoredValue(value: string): string {
  return formatDisplayValue(value)
}

export function formatRequirementLabel(module: string, metric: string): string {
  return `${sourceLabel(module)} · ${formatDisplayLabel(metric)}`
}

export function factsByCid(facts: Fact[] | undefined): Record<string, Fact> {
  const map: Record<string, Fact> = {}
  for (const fact of facts ?? []) {
    const cid = fact.citation?.cid
    if (cid) map[cid] = fact
  }
  return map
}

/** How many rows produced the figure. The ids themselves are not a reading surface. */
export function formatRecordCount(
  recordIds: string[] | null | undefined,
): string | null {
  const n = recordIds?.filter(Boolean).length ?? 0
  if (n === 0) return null
  return n === 1 ? '1 record' : `${n} records`
}
