import { describe, expect, it } from 'vitest'

import { incidentPath, logPath, withManual } from '@/lib/whatsapp-paths'

describe('whatsapp paths', () => {
  it('namespaces paths by row kind, matching the backend vocabulary', () => {
    expect(incidentPath('3', 'corporation')).toBe('incident:3.corporation')
    expect(logPath('3', 'quantity')).toBe('log:3.quantity')
  })

  it('appends a path without duplicating an existing one', () => {
    expect(withManual(['as_at'], 'incident:1.corporation')).toEqual([
      'as_at',
      'incident:1.corporation',
    ])
    expect(withManual(['as_at'], 'as_at')).toEqual(['as_at'])
  })
})
