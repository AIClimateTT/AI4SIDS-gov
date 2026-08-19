import { describe, expect, it } from 'vitest'

import {
  casualtyOccurred,
  formToCaptureIncident,
  formToCaptureLog,
  nextIncidentRowId,
  parseOptionalNumber,
} from '@/lib/capture-mapping'

describe('capture mapping', () => {
  it('assigns the next integer row id', () => {
    expect(nextIncidentRowId([])).toBe('1')
    expect(nextIncidentRowId([{ row_id: '1' }, { row_id: '3' }])).toBe('4')
  })

  it('maps a form to a capture incident with casualty defaults from counts', () => {
    const incident = formToCaptureIncident(
      {
        community: 'Petit Valley',
        street: '',
        incident_type: 'flooding',
        incident_summary: '5 houses flooded',
        event_date: '2026-08-18',
        injuries_count: '2',
        deaths_count: '',
      },
      '1',
    )

    expect(incident.row_id).toBe('1')
    expect(incident.community).toBe('Petit Valley')
    expect(incident.street).toBeNull()
    expect(incident.injuries_count).toBe(2)
    expect(incident.injuries_occurred).toBe(true)
    expect(incident.deaths_count).toBeNull()
    expect(incident.deaths_occurred).toBeNull()
  })

  it('treats a zero count as no casualties occurred', () => {
    expect(casualtyOccurred(0)).toBe(false)
    expect(parseOptionalNumber('0')).toBe(0)
    expect(formToCaptureIncident(
      {
        community: '',
        street: '',
        incident_type: 'fire',
        incident_summary: 'Shed burned',
        event_date: '2026-08-18',
        injuries_count: '0',
        deaths_count: '0',
      },
      '2',
    ).injuries_occurred).toBe(false)
  })

  it('maps a log form including a structured quantity', () => {
    expect(
      formToCaptureLog(
        {
          category: 'resource',
          statement: '200 sandbags remaining at depot',
          item: 'sandbags',
          quantity: '200',
          unit: 'bags',
          status: 'available',
        },
        '1',
      ),
    ).toEqual({
      row_id: '1',
      category: 'resource',
      statement: '200 sandbags remaining at depot',
      item: 'sandbags',
      quantity: 200,
      unit: 'bags',
      status: 'available',
    })
  })

  it('maps a not-set log status to null', () => {
    expect(
      formToCaptureLog(
        {
          category: 'activity',
          statement: 'Informed the CEO',
          item: '',
          quantity: '',
          unit: '',
          status: 'none',
        },
        '2',
      ).status,
    ).toBeNull()
  })
})
