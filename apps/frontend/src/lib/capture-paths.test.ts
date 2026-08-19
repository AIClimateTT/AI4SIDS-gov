import { describe, expect, it } from 'vitest'

import { incidentPath, logPath, withManual } from '@/lib/capture-paths'

describe('capture paths', () => {
  it('namespaces paths by row kind, matching the backend vocabulary', () => {
    expect(incidentPath('3', 'injuries_count')).toBe('incident:3.injuries_count')
    expect(logPath('3', 'quantity')).toBe('log:3.quantity')
  })

  it('appends a path without duplicating an existing one', () => {
    expect(withManual(['alert_level'], 'incident:1.community')).toEqual([
      'alert_level',
      'incident:1.community',
    ])
    expect(withManual(['alert_level'], 'alert_level')).toEqual(['alert_level'])
  })
})
