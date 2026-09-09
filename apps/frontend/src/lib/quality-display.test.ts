import { describe, expect, it } from 'vitest'

import {
  chartAxisPercent,
  formatThresholdValue,
  isLowerBetter,
  thresholdStatusLabel,
} from '@/lib/quality-display'

describe('formatThresholdValue', () => {
  it('formats 0-1 rates as percents', () => {
    expect(formatThresholdValue('completeness', 0.99)).toBe('99%')
    expect(formatThresholdValue('citation_accuracy', 0.95)).toBe('95%')
  })

  it('formats usability mean on a 1-5 scale', () => {
    expect(formatThresholdValue('usability_mean', 4.2)).toBe('4.2 / 5')
  })

  it('does not treat usability mean as a percent', () => {
    expect(formatThresholdValue('usability_mean', 4.2)).not.toContain('420')
  })

  it('renders an em dash when the value is missing', () => {
    expect(formatThresholdValue('faithfulness', null)).toBe('—')
  })
})

describe('chartAxisPercent', () => {
  it('maps a rate onto a 0-100 axis', () => {
    expect(chartAxisPercent('completeness', 0.99)).toBe(99)
  })

  it('maps usability mean onto the same axis via / 5', () => {
    expect(chartAxisPercent('usability_mean', 4)).toBe(80)
  })

  it('returns null when the value is missing', () => {
    expect(chartAxisPercent('faithfulness', null)).toBeNull()
  })
})

describe('isLowerBetter', () => {
  it('marks hallucination and unsupported claim as lower-is-better', () => {
    expect(isLowerBetter('critical_hallucination')).toBe(true)
    expect(isLowerBetter('unsupported_claim')).toBe(true)
  })

  it('treats other KPIs as higher-is-better', () => {
    expect(isLowerBetter('completeness')).toBe(false)
    expect(isLowerBetter('usability_mean')).toBe(false)
  })
})

describe('thresholdStatusLabel', () => {
  it('labels met, missed, and waiting rows', () => {
    expect(thresholdStatusLabel(true)).toBe('Met')
    expect(thresholdStatusLabel(false)).toBe('Below')
    expect(thresholdStatusLabel(null)).toBe('Waiting')
  })
})
