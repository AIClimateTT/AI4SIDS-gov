import { sourceLabel } from '@/components/shared/source-badge'
import {
  CORPORATION_LABELS,
  isCanonicalCorporation,
} from '@/lib/corporations'
import { formatConstant } from '@/lib/format-constant'
import type { Fact } from '@/types/dmcu'

/** Reader-facing name for citation.query_ref. The JSON field does not change. */
export const SOURCE_QUERY_LABEL = 'Source query'

/** Reader-facing name for citation.as_of. The JSON field does not change. */
export const AS_OF_LABEL = 'As of'

/** A slug with at least one underscore, e.g. incidents_by_corporation. */
const SNAKE_CASE_RE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/

export function formatFactValue(fact: Pick<Fact, 'value' | 'unit'>): string {
  const unit = fact.unit ? ` ${fact.unit}` : ''
  return `${fact.value}${unit}`
}

export function formatMetricLabel(metric: string): string {
  return formatConstant(metric)
}

/**
 * Values stored as slugs or snake_case constants, shown to a reader.
 * Corporation ids become the corporation's name; other snake_case becomes
 * Title Case; dates and free text pass through.
 */
export function humanizeStoredValue(value: string): string {
  if (isCanonicalCorporation(value)) return CORPORATION_LABELS[value]
  if (SNAKE_CASE_RE.test(value)) return formatConstant(value)
  return value
}

export function formatRequirementLabel(module: string, metric: string): string {
  return `${sourceLabel(module)} · ${formatConstant(metric)}`
}

export function factsByCid(facts: Fact[] | undefined): Record<string, Fact> {
  const map: Record<string, Fact> = {}
  for (const fact of facts ?? []) {
    const cid = fact.citation?.cid
    if (cid) map[cid] = fact
  }
  return map
}
