import { describe, expect, it } from 'vitest'

import {
  CANONICAL_CORPORATIONS,
  CORPORATION_LABELS,
  isCanonicalCorporation,
} from '@/lib/corporations'

describe('isCanonicalCorporation', () => {
  it('accepts all fourteen canonical slugs', () => {
    for (const corporation of CANONICAL_CORPORATIONS) {
      expect(isCanonicalCorporation(corporation)).toBe(true)
    }
    expect(CANONICAL_CORPORATIONS).toHaveLength(14)
  })

  it('rejects a slug outside the fourteen', () => {
    // The reason this guard exists: an unknown slug matches no rows, so every
    // count comes back zero and the page reads as an authoritative "nothing
    // happened" for a region that may have filed plenty.
    expect(isCanonicalCorporation('port_of_spain')).toBe(false)
    expect(isCanonicalCorporation('diego_martin_regional_corporation')).toBe(
      false,
    )
  })

  it('rejects non-strings and empty input', () => {
    expect(isCanonicalCorporation(undefined)).toBe(false)
    expect(isCanonicalCorporation(null)).toBe(false)
    expect(isCanonicalCorporation('')).toBe(false)
    expect(isCanonicalCorporation(14)).toBe(false)
  })

  it('is case sensitive, matching the export exactly', () => {
    expect(isCanonicalCorporation('ARIMA_BOROUGH_CORPORATION')).toBe(false)
  })
})

describe('CORPORATION_LABELS', () => {
  it('gives every canonical slug a display label', () => {
    // The slugs are truncated to 31 characters by the Survey123 export, so a
    // label derived from the id reads "Diego Martin Regional Corporati".
    for (const corporation of CANONICAL_CORPORATIONS) {
      expect(CORPORATION_LABELS[corporation]).toBeTruthy()
      expect(CORPORATION_LABELS[corporation]).not.toBe(corporation)
    }
  })
})
