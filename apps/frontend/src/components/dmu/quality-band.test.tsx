// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualityBand } from './quality-band'
import type { QualitySummary } from '@/types/dmcu'

function summary(
  overrides: Partial<QualitySummary> = {},
): QualitySummary {
  return {
    report_count: 4,
    scored_count: 4,
    rating_count: 0,
    rating_mean: null,
    rating_positive_rate: null,
    task_started: 0,
    task_succeeded_unaided: 0,
    thresholds: [
      {
        name: 'completeness',
        threshold: 0.95,
        actual: 0.99,
        met: true,
        sample: 4,
      },
      {
        name: 'critical_numerical',
        threshold: 1,
        actual: 0.5,
        met: false,
        sample: 4,
      },
    ],
    ...overrides,
  }
}

describe('QualityBand', () => {
  it('shows passing and failing threshold names', () => {
    render(<QualityBand summary={summary()} />)
    expect(screen.getByText(/completeness/i)).toBeTruthy()
    expect(screen.getByText(/critical numerical/i)).toBeTruthy()
  })

  it('is quiet when nothing has been scored', () => {
    render(<QualityBand summary={summary({ scored_count: 0, thresholds: [] })} />)
    expect(screen.getByText('No scored reports yet.')).toBeTruthy()
  })
})
