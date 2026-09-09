import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  STORAGE_PREF_KEY,
  STORED_AT_KEY,
  TIMED_SESSION_MAX_AGE_MS,
} from '@/lib/auth/constants'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '@/lib/auth/storage'
import { decodeJwtPayload, isTokenExpired } from '@/lib/auth/token'

function encodeJwt(payload: object): string {
  const header = Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString(
    'base64url',
  )
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url')
  return `${header}.${body}.sig`
}

const mem: Record<string, string> = {}
const storage = {
  getItem: (key: string) => (key in mem ? mem[key] : null),
  setItem: (key: string, value: string) => {
    mem[key] = value
  },
  removeItem: (key: string) => {
    delete mem[key]
  },
  clear: () => {
    for (const key of Object.keys(mem)) delete mem[key]
  },
}

beforeEach(() => {
  storage.clear()
  const win = globalThis as typeof globalThis & Window
  Object.defineProperty(win, 'localStorage', {
    value: storage,
    configurable: true,
  })
  win.dispatchEvent = () => true
  Object.defineProperty(globalThis, 'window', {
    value: win,
    configurable: true,
  })
})

afterEach(() => {
  storage.clear()
})

describe('decodeJwtPayload', () => {
  it('reads the payload segment', () => {
    const token = encodeJwt({ sub: 'user-1', role: 'dmu', exp: 1 })
    expect(decodeJwtPayload(token)).toMatchObject({
      sub: 'user-1',
      role: 'dmu',
    })
  })

  it('returns null for garbage', () => {
    expect(decodeJwtPayload('not-a-jwt')).toBeNull()
  })
})

describe('isTokenExpired', () => {
  it('treats a missing exp as expired', () => {
    expect(isTokenExpired(encodeJwt({ sub: 'x' }), 0)).toBe(true)
  })

  it('respects the expiry buffer', () => {
    const exp = Math.floor(Date.now() / 1000) + 30
    expect(isTokenExpired(encodeJwt({ sub: 'x', exp }), 60)).toBe(true)
    expect(isTokenExpired(encodeJwt({ sub: 'x', exp }), 0)).toBe(false)
  })
})

describe('token storage', () => {
  it('stores and returns a permanent session', () => {
    setTokens('access', 'refresh', true)
    expect(getAccessToken()).toBe('access')
    expect(getRefreshToken()).toBe('refresh')
    expect(localStorage.getItem(STORAGE_PREF_KEY)).toBe('permanent')
  })

  it('clears a timed session after the idle TTL', () => {
    setTokens('access', 'refresh', false)
    const storedAt = Date.now() - TIMED_SESSION_MAX_AGE_MS - 1
    localStorage.setItem(STORED_AT_KEY, String(storedAt))

    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
  })

  it('clearTokens removes every auth key', () => {
    setTokens('access', 'refresh', true)
    clearTokens()
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })
})
