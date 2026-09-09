// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualityThresholdTable } from './quality-threshold-table'
import type { ThresholdStatus } from '@/types/dmcu'

const rows: ThresholdStatus[] = [
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
  {
    name: 'critical_hallucination',
    threshold: 0,
    actual: 0,
    met: true,
    sample: 4,
  },
]

describe('QualityThresholdTable', () => {
  it('shows passing and failing KPI names with status and sample', () => {
    render(<QualityThresholdTable thresholds={rows} />)
    expect(screen.getByText('Completeness')).toBeTruthy()
    expect(screen.getByText('Critical Numerical')).toBeTruthy()
    expect(screen.getByText('99%')).toBeTruthy()
    expect(screen.getByText('50%')).toBeTruthy()
    expect(screen.getAllByText('4').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Met').length).toBeGreaterThan(0)
    expect(screen.getByText('Below')).toBeTruthy()
  })

  it('notes when a lower rate is the better outcome', () => {
    render(<QualityThresholdTable thresholds={rows} />)
    expect(screen.getAllByText(/lower is better/i).length).toBeGreaterThan(0)
  })
})
