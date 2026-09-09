const LOWER_BETTER = new Set(['critical_hallucination', 'unsupported_claim'])

export function isLowerBetter(name: string): boolean {
  return LOWER_BETTER.has(name)
}

export function formatThresholdValue(
  name: string,
  value: number | null,
): string {
  if (value === null) return '—'
  if (name === 'usability_mean') return `${value.toFixed(1)} / 5`
  return `${Math.round(value * 100)}%`
}

export function chartAxisPercent(
  name: string,
  value: number | null,
): number | null {
  if (value === null) return null
  if (name === 'usability_mean') return Math.round((value / 5) * 100)
  return Math.round(value * 100)
}

export function thresholdStatusLabel(
  met: boolean | null,
): 'Met' | 'Below' | 'Waiting' {
  if (met === true) return 'Met'
  if (met === false) return 'Below'
  return 'Waiting'
}
