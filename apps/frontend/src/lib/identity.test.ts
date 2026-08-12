import { describe, expect, it } from 'vitest'

import { CANONICAL_CORPORATIONS } from '@/lib/corporations'
import {
  IDENTITY_STORAGE_KEY,
  clearIdentity,
  identityHomePath,
  identityLabel,
  loadIdentity,
  parseIdentity,
  saveIdentity,
  serializeIdentity,
  type Identity,
  type IdentityStorage,
} from '@/lib/identity'

const DIEGO_MARTIN = 'diego_martin_regional_corporati'

function fakeStorage(initial: Record<string, string> = {}): IdentityStorage & {
  values: Record<string, string>
} {
  const values = { ...initial }
  return {
    values,
    getItem: (key: string) => (key in values ? values[key] : null),
    setItem: (key: string, value: string) => {
      values[key] = value
    },
    removeItem: (key: string) => {
      delete values[key]
    },
  }
}

function throwingStorage(): IdentityStorage {
  return {
    getItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
    setItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
    removeItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
  }
}

describe('parseIdentity', () => {
  it('accepts the DMU role', () => {
    expect(parseIdentity('{"role":"dmu"}')).toEqual({ role: 'dmu' })
  })

  it('accepts a corp role with a canonical corporation', () => {
    expect(parseIdentity(`{"role":"corp","corporation":"${DIEGO_MARTIN}"}`)).toEqual({
      role: 'corp',
      corporation: DIEGO_MARTIN,
    })
  })

  it('rejects a corporation that is not one of the fourteen', () => {
    expect(
      parseIdentity('{"role":"corp","corporation":"atlantis_city_corporation"}'),
    ).toBeNull()
  })

  it('rejects a corp role with no corporation', () => {
    expect(parseIdentity('{"role":"corp"}')).toBeNull()
  })

  it('rejects an unknown role', () => {
    expect(parseIdentity('{"role":"minister"}')).toBeNull()
  })

  it('returns null for null, empty, malformed and non-object input', () => {
    expect(parseIdentity(null)).toBeNull()
    expect(parseIdentity('')).toBeNull()
    expect(parseIdentity('not json at all')).toBeNull()
    expect(parseIdentity('"a string"')).toBeNull()
    expect(parseIdentity('null')).toBeNull()
    expect(parseIdentity('[]')).toBeNull()
  })
})

describe('round trip', () => {
  it('survives serialize then parse for both roles', () => {
    const dmu: Identity = { role: 'dmu' }
    const corp: Identity = { role: 'corp', corporation: DIEGO_MARTIN }

    expect(parseIdentity(serializeIdentity(dmu))).toEqual(dmu)
    expect(parseIdentity(serializeIdentity(corp))).toEqual(corp)
  })
})

describe('storage', () => {
  it('saves under the shared key and loads it back', () => {
    const storage = fakeStorage()
    const identity: Identity = { role: 'corp', corporation: DIEGO_MARTIN }

    saveIdentity(storage, identity)

    expect(storage.values[IDENTITY_STORAGE_KEY]).toBe(serializeIdentity(identity))
    expect(loadIdentity(storage)).toEqual(identity)
  })

  it('loads null when nothing is stored', () => {
    expect(loadIdentity(fakeStorage())).toBeNull()
  })

  it('loads null when the stored value is corrupt, rather than throwing', () => {
    const storage = fakeStorage({ [IDENTITY_STORAGE_KEY]: '{oh no' })

    expect(loadIdentity(storage)).toBeNull()
  })

  it('clears the stored identity', () => {
    const storage = fakeStorage()
    saveIdentity(storage, { role: 'dmu' })

    clearIdentity(storage)

    expect(loadIdentity(storage)).toBeNull()
  })

  it('degrades to no identity when storage itself throws', () => {
    // Safari in private mode throws on access. A crash here would take the
    // whole app down on first paint, so every access is wrapped.
    const storage = throwingStorage()

    expect(loadIdentity(storage)).toBeNull()
    expect(() => saveIdentity(storage, { role: 'dmu' })).not.toThrow()
    expect(() => clearIdentity(storage)).not.toThrow()
  })
})

describe('display helpers', () => {
  it('labels the DMU with its full name', () => {
    expect(identityLabel({ role: 'dmu' })).toBe(
      'Disaster Management Coordinating Unit',
    )
  })

  it('labels a corporation with its full untruncated name', () => {
    // Guards the truncation: deriving this from the id would yield
    // "Diego Martin Regional Corporati".
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
    expect(identityHomePath({ role: 'dmu' })).toBe('/dmu')
    expect(identityHomePath({ role: 'corp', corporation: DIEGO_MARTIN })).toBe('/corp')
  })
})
