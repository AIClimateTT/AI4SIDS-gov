import {
  CORPORATION_LABELS,
  isCanonicalCorporation,
} from '@/lib/corporations'
import { formatConstant } from '@/lib/format-constant'

const UNKNOWN = '—'

/** `{corporation}` style template placeholders — keep the braces, do not title-case. */
const PLACEHOLDER_RE = /^\{[^{}]+\}$/

/** ISO dates must not be treated as kebab-case slugs. */
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$/

/**
 * A stored identifier: `date_from`, `community`, `relief-supplied`.
 * Mixed-case or spaced text is already a label and is left alone.
 */
const IDENTIFIER_RE = /^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$/

/**
 * Turn a stored key or slug into a label an officer can read.
 *
 * Snake_case and kebab-case become Title Case. Emails, dates, placeholders,
 * and already-written labels pass through. Empty becomes an em dash.
 */
export function formatDisplayLabel(
  value: string | null | undefined,
): string {
  if (value == null) return UNKNOWN
  const trimmed = value.trim()
  if (trimmed === '') return UNKNOWN
  if (trimmed.includes('@') || PLACEHOLDER_RE.test(trimmed) || ISO_DATE_RE.test(trimmed)) {
    return trimmed
  }
  if (IDENTIFIER_RE.test(trimmed) || trimmed.includes('_')) {
    return formatConstant(trimmed.replaceAll('-', '_'))
  }
  return trimmed
}

/**
 * Turn a stored value into reader-facing text.
 *
 * Canonical corporation ids become the corporation's name. Other identifiers
 * go through {@link formatDisplayLabel}.
 */
export function formatDisplayValue(
  value: string | number | boolean | null | undefined,
): string {
  if (value == null || value === '') return UNKNOWN
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (isCanonicalCorporation(value)) return CORPORATION_LABELS[value]
  return formatDisplayLabel(value)
}

/**
 * Render a params/filter record as `Date From: 2024-06-01 · Corporation: Arima Borough Corporation`.
 *
 * This is the form that used to leak `date_from=diego_martin_regional_corporati`
 * into tables.
 */
export function formatDisplayPairs(
  record:
    | Record<string, string | number | boolean | null | undefined>
    | null
    | undefined,
  separator = ' · ',
): string {
  const entries = Object.entries(record ?? {}).filter(
    ([, item]) => item != null && item !== '',
  )
  if (entries.length === 0) return UNKNOWN
  return entries
    .map(([key, item]) => `${formatDisplayLabel(key)}: ${formatDisplayValue(item)}`)
    .join(separator)
}
