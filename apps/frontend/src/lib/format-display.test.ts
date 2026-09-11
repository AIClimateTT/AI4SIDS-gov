import { describe, expect, it } from 'vitest'

import {
  formatDisplayLabel,
  formatDisplayPairs,
  formatDisplayValue,
} from './format-display'

describe('formatDisplayLabel', () => {
  it('title-cases snake_case keys', () => {
    expect(formatDisplayLabel('date_from')).toBe('Date From')
    expect(formatDisplayLabel('incident_type')).toBe('Incident Type')
  })

  it('title-cases a single lowercase identifier', () => {
    expect(formatDisplayLabel('community')).toBe('Community')
  })

  it('leaves emails, dates, and placeholders alone', () => {
    expect(formatDisplayLabel('ada_lovelace@example.com')).toBe(
      'ada_lovelace@example.com',
    )
    expect(formatDisplayLabel('2024-06-01')).toBe('2024-06-01')
    expect(formatDisplayLabel('{date_from}')).toBe('{date_from}')
  })

  it('leaves already-written labels alone', () => {
    expect(formatDisplayLabel('Diego Martin')).toBe('Diego Martin')
  })

  it('uses an em dash for empty values', () => {
    expect(formatDisplayLabel(null)).toBe('—')
    expect(formatDisplayLabel('')).toBe('—')
  })
})

describe('formatDisplayValue', () => {
  it('replaces a corporation slug with the corporation name', () => {
    expect(formatDisplayValue('arima_borough_corporation')).toBe(
      'Arima Borough Corporation',
    )
  })

  it('title-cases other stored identifiers', () => {
    expect(formatDisplayValue('relief_distributed')).toBe('Relief Distributed')
    expect(formatDisplayValue('minister_situation_report')).toBe(
      'Minister Situation Report',
    )
  })

  it('stringifies numbers and booleans', () => {
    expect(formatDisplayValue(3)).toBe('3')
    expect(formatDisplayValue(true)).toBe('true')
  })
})

describe('formatDisplayPairs', () => {
  it('renders keys and values without underscores', () => {
    expect(
      formatDisplayPairs({
        date_from: '2024-06-01',
        corporation: 'diego_martin_regional_corporati',
      }),
    ).toBe(
      'Date From: 2024-06-01 · Corporation: Diego Martin Regional Corporation',
    )
  })

  it('uses an em dash when there is nothing to show', () => {
    expect(formatDisplayPairs({})).toBe('—')
    expect(formatDisplayPairs(null)).toBe('—')
  })
})
