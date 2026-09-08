import { describe, expect, it } from 'vitest'

import { currentUserIdFromToken, userDisplayName } from './users'

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
