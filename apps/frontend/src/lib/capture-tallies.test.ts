import { describe, expect, it } from 'vitest'

import { workingSetTallies } from '@/lib/capture-tallies'
import type { CaptureIncident } from '@/types/dmcu'

function incident(overrides: Partial<CaptureIncident> = {}): CaptureIncident {
  return {
    row_id: '1',
    community: 'Petit Valley',
    street: null,
    incident_type: 'flooding',
    raw_incident_type: null,
    incident_summary: 'Flooding',
    event_date: '2026-08-18',
    injuries_occurred: false,
    injuries_count: 0,
    deaths_occurred: false,
    deaths_count: 0,
    building_damage: null,
    special_needs_occupants: null,
    estimated_damage_cost: null,
    action_taken: null,
    relief_supplied: null,
    forwarded_to_agency: null,
    further_assessment_required: null,
    other_follow_up: null,
    ...overrides,
  }
}

describe('workingSetTallies', () => {
  it('sums known injury and death counts, treating null as zero', () => {
    const tallies = workingSetTallies([
      incident({ row_id: '1', injuries_occurred: true, injuries_count: 2, deaths_count: 1, deaths_occurred: true }),
      incident({ row_id: '2', injuries_count: null, injuries_occurred: false, deaths_count: null, deaths_occurred: false }),
    ])
    expect(tallies.incidents).toBe(2)
    expect(tallies.injuries).toBe(2)
    expect(tallies.deaths).toBe(1)
  })

  it('counts a row as unknown casualties only when all four fields are null', () => {
    const tallies = workingSetTallies([
      incident({
        row_id: '1',
        injuries_count: null,
        injuries_occurred: null,
        deaths_count: null,
        deaths_occurred: null,
      }),
      incident({ row_id: '2', injuries_count: 0, injuries_occurred: false }),
    ])
    expect(tallies.unknownCasualties).toBe(1)
  })

  it('does not treat a known-zero casualty row as unknown', () => {
    const tallies = workingSetTallies([
      incident({ injuries_count: 0, injuries_occurred: false, deaths_count: 0, deaths_occurred: false }),
    ])
    expect(tallies.unknownCasualties).toBe(0)
    expect(tallies.injuries).toBe(0)
    expect(tallies.deaths).toBe(0)
  })

  it('counts relief supplied and further assessment only when true', () => {
    const tallies = workingSetTallies([
      incident({ row_id: '1', relief_supplied: true, further_assessment_required: true }),
      incident({ row_id: '2', relief_supplied: false, further_assessment_required: null }),
      incident({ row_id: '3', relief_supplied: true, further_assessment_required: false }),
    ])
    expect(tallies.reliefSupplied).toBe(2)
    expect(tallies.furtherAssessment).toBe(1)
  })
})
