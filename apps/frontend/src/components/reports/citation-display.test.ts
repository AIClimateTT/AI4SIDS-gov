import { describe, expect, it } from 'vitest'

import {
  AS_OF_LABEL,
  SOURCE_QUERY_LABEL,
  factsByCid,
  formatFactValue,
  formatMetricLabel,
  formatRequirementLabel,
  humanizeStoredValue,
} from '@/components/reports/citation-display'
import type { Fact } from '@/types/dmcu'

function fact(overrides: Partial<Fact> = {}): Fact {
  return {
    metric: 'incidents_by_corporation',
    value: 42,
    unit: 'incidents',
    scope: { corporation: 'arima_borough_corporation' },
    breakdown: null,
    verification: 'validated',
    citation: {
      cid: 'C001',
      module: 'survey123',
      description: 'Arima incident count',
      query_ref: 'incidents_by_corporation(corporation=arima_borough_corporation)',
      record_ids: null,
      as_of: '2025-05-18T16:42:00Z',
    },
    ...overrides,
  }
}

describe('citation display labels', () => {
  it('names the lookup string Source query, not query_ref', () => {
    expect(SOURCE_QUERY_LABEL).toBe('Source query')
    expect(SOURCE_QUERY_LABEL).not.toContain('query_ref')
  })

  it('names the timestamp As of, not as_of', () => {
    expect(AS_OF_LABEL).toBe('As of')
    expect(AS_OF_LABEL).not.toContain('as_of')
  })
})

describe('formatFactValue', () => {
  it('joins the figure and its unit', () => {
    expect(formatFactValue(fact())).toBe('42 incidents')
  })

  it('omits a trailing space when there is no unit', () => {
    expect(formatFactValue(fact({ unit: null, value: 3 }))).toBe('3')
  })
})

describe('formatMetricLabel', () => {
  it('turns a metric slug into a readable label', () => {
    expect(formatMetricLabel('incidents_by_corporation')).toBe(
      'Incidents By Corporation',
    )
  })
})

describe('humanizeStoredValue', () => {
  it('replaces a corporation slug with the corporation name', () => {
    expect(humanizeStoredValue('arima_borough_corporation')).toBe(
      'Arima Borough Corporation',
    )
  })

  it('title-cases other snake_case keys', () => {
    expect(humanizeStoredValue('include_pending')).toBe('Include Pending')
  })

  it('leaves a date or free-text value alone', () => {
    expect(humanizeStoredValue('2025-05-01')).toBe('2025-05-01')
    expect(humanizeStoredValue('Diego Martin')).toBe('Diego Martin')
  })
})

describe('formatRequirementLabel', () => {
  it('names the source and metric in words, not module.metric', () => {
    expect(formatRequirementLabel('survey123', 'incident_count')).toBe(
      'Field · Incident Count',
    )
    expect(formatRequirementLabel('sitreps', 'relief_stock_summary')).toBe(
      'SITREP · Relief Stock Summary',
    )
  })
})

describe('factsByCid', () => {
  it('indexes facts by their citation id', () => {
    const second = fact({
      citation: { ...fact().citation, cid: 'C007', module: 'sitreps' },
    })
    expect(factsByCid([fact(), second]).C001.citation.module).toBe('survey123')
    expect(factsByCid([fact(), second]).C007.citation.module).toBe('sitreps')
  })

  it('returns an empty map when there are no facts', () => {
    expect(factsByCid(undefined)).toEqual({})
  })
})
