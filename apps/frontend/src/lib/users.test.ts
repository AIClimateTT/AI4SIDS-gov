import { describe, expect, it } from 'vitest'

import { currentUserIdFromToken, userDisplayName, corporationDisplayName } from './users'

describe('userDisplayName', () => {
  it('joins first and last name', () => {
    expect(
      userDisplayName({ first_name: 'Ada', last_name: 'Lovelace' }),
    ).toBe('Ada Lovelace')
  })

  it('falls back to an em dash when both names are missing', () => {
    expect(userDisplayName({ first_name: null, last_name: null })).toBe('—')
  })
})

describe('corporationDisplayName', () => {
  it('uses the corporation proper name', () => {
    expect(corporationDisplayName('arima_borough_corporation')).toBe(
      'Arima Borough Corporation',
    )
  })

  it('falls back to an em dash when there is no corporation', () => {
    expect(corporationDisplayName(null)).toBe('—')
  })

  it('title-cases an unknown corporation slug instead of showing underscores', () => {
    expect(corporationDisplayName('new_city_corporation')).toBe(
      'New City Corporation',
    )
  })
})

describe('currentUserIdFromToken', () => {
  it('reads sub from a JWT payload', () => {
    const payload = btoa(JSON.stringify({ sub: 'user-123' }))
    expect(currentUserIdFromToken(`aaa.${payload}.sig`)).toBe('user-123')
  })

  it('returns null for missing or malformed tokens', () => {
    expect(currentUserIdFromToken(null)).toBeNull()
    expect(currentUserIdFromToken('not-a-jwt')).toBeNull()
  })
})
