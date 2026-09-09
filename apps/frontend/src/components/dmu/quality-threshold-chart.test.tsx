// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { QualityThresholdChart } from './quality-threshold-chart'
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
]

describe('QualityThresholdChart', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      get: () => 800,
    })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get: () => 320,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('labels the chart and the KPIs it plots', () => {
    render(<QualityThresholdChart thresholds={rows} />)
    expect(
      screen.getByRole('img', { name: 'Actual versus threshold' }),
    ).toBeTruthy()
    expect(screen.getByText('Completeness')).toBeTruthy()
    expect(screen.getByText('Critical Numerical')).toBeTruthy()
  })
})
