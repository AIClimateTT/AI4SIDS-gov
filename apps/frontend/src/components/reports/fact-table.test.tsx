// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ReportFactTable } from '@/components/reports/fact-table'
import type { Fact, FactTable } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

function fact(overrides: Partial<Fact> = {}): Fact {
  return {
    metric: 'incidents_by_corporation',
    value: 10,
    unit: 'incidents',
    scope: {},
    breakdown: null,
    verification: 'validated',
    citation: {
      cid: 'C001',
      module: 'survey123',
      description: 'Arima incidents',
      query_ref: 'incidents_by_corporation()',
      record_ids: null,
      as_of: '2025-05-18T16:42:00Z',
    },
    ...overrides,
  }
}

function table(facts: Fact[]): FactTable {
  return { facts }
}

describe('ReportFactTable', () => {
  it('shows the metric and verification in words, not slugs', () => {
    render(<ReportFactTable factTable={table([fact()])} />)

    expect(screen.getByText('Incidents By Corporation')).toBeTruthy()
    expect(screen.getByText('Validated')).toBeTruthy()
    expect(screen.queryByText('incidents_by_corporation')).toBeNull()
    expect(screen.queryByText('validated')).toBeNull()
  })

  it('names a corporation breakdown key rather than echoing the slug', () => {
    render(
      <ReportFactTable
        factTable={table([
          fact({
            breakdown: { arima_borough_corporation: 10 },
          }),
        ])}
      />,
    )

    expect(screen.getByText('Arima Borough Corporation')).toBeTruthy()
    expect(screen.queryByText('arima_borough_corporation')).toBeNull()
  })
})
