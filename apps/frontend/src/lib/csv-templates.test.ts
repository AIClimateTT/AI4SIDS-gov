import { describe, expect, it } from 'vitest'

import {
  INCIDENT_CSV_HEADERS,
  LOG_CSV_HEADERS,
  csvTemplateText,
} from '@/lib/csv-templates'

describe('csv templates', () => {
  it('matches the exact headers the incident parser reads', () => {
    // Nobody can guess "Further Assessment Required". These strings must stay
    // in step with parse_incident_row in the backend.
    expect(INCIDENT_CSV_HEADERS).toEqual([
      'Row ID', 'Community', 'Street', 'Incident Type', 'Date of Event',
      'Incident Summary', 'Injuries Occurred', 'Injuries Count',
      'Deaths Occurred', 'Deaths Count', 'Building Damage',
      'Special Needs Occupants', 'Estimated Damage Cost', 'Action Taken',
      'Relief Supplied', 'Forwarded To Agency', 'Further Assessment Required',
      'Other Follow Up',
    ])
  })

  it('matches the exact headers the log parser reads', () => {
    expect(LOG_CSV_HEADERS).toEqual([
      'Category', 'Statement', 'Item', 'Quantity', 'Unit', 'Status',
    ])
  })

  it('renders a header-only csv', () => {
    expect(csvTemplateText(['A', 'B'])).toBe('A,B\n')
  })

  it('quotes a header containing a comma', () => {
    expect(csvTemplateText(['A,B', 'C'])).toBe('"A,B",C\n')
  })
})
