import { describe, expect, it } from 'vitest'

import { CANONICAL_CORPORATIONS } from '@/lib/corporations'
import {
  identityHomePath,
  identityLabel,
  sessionToIdentity,
  type Identity,
} from '@/lib/identity'

const DIEGO_MARTIN = 'diego_martin_regional_corporati'

describe('sessionToIdentity', () => {
  it('maps a DMU session', () => {
    expect(sessionToIdentity({ role: 'dmu' })).toEqual({ role: 'dmu' })
  })

  it('maps a corp session with a canonical corporation', () => {
    expect(
      sessionToIdentity({ role: 'corp', corporation: DIEGO_MARTIN }),
    ).toEqual({
      role: 'corp',
      corporation: DIEGO_MARTIN,
    })
  })

  it('rejects a corporation that is not one of the fourteen', () => {
    expect(
      sessionToIdentity({
        role: 'corp',
        corporation: 'atlantis_city_corporation',
      }),
    ).toBeNull()
  })

  it('rejects a corp role with no corporation', () => {
    expect(sessionToIdentity({ role: 'corp' })).toBeNull()
  })

  it('rejects an unknown role', () => {
    expect(sessionToIdentity({ role: 'minister' })).toBeNull()
  })

  it('returns null for a missing session', () => {
    expect(sessionToIdentity(null)).toBeNull()
  })
})

describe('display helpers', () => {
  it('labels the DMU with its full name', () => {
    expect(identityLabel({ role: 'dmu' })).toBe(
      'Disaster Management Coordinating Unit',
    )
  })

  it('labels a corporation with its full untruncated name', () => {
    expect(identityLabel({ role: 'corp', corporation: DIEGO_MARTIN })).toBe(
      'Diego Martin Regional Corporation',
    )
  })

  it('has a label for every canonical corporation', () => {
    for (const corporation of CANONICAL_CORPORATIONS) {
      const label = identityLabel({ role: 'corp', corporation })
      expect(label).toBeTruthy()
      expect(label).not.toMatch(/Corporati$/)
    }
  })

  it('routes each role to its own home', () => {
    const corp: Identity = { role: 'corp', corporation: DIEGO_MARTIN }
    expect(identityHomePath({ role: 'dmu' })).toBe('/dmu')
    expect(identityHomePath(corp)).toBe('/corp')
  })
})
