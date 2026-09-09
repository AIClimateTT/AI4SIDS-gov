import { API_BASE_URL, AUTH_ENDPOINT_PREFIX } from '@/lib/auth/constants'
import {
  clearTokens,
  getRefreshToken,
  getRememberMe,
  setTokens,
} from '@/lib/auth/storage'
import { isTokenExpired } from '@/lib/auth/token'
import type { AuthTokenResponse } from '@/lib/auth/types'

export class AuthUnavailableError extends Error {
  constructor(message = 'Auth service unavailable') {
    super(message)
    this.name = 'AuthUnavailableError'
  }
}

let inFlight: Promise<string> | null = null
let unavailableUntil = 0

async function doRefresh(): Promise<string> {
  if (Date.now() < unavailableUntil) {
    throw new AuthUnavailableError()
  }
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearTokens()
    throw new Error('Not authenticated')
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  } catch {
    unavailableUntil = Date.now() + 30_000
    throw new AuthUnavailableError()
  }
  if (res.status === 401 || res.status === 403) {
    clearTokens()
    throw new Error('Session expired')
  }
  if (!res.ok) {
    unavailableUntil = Date.now() + 30_000
    throw new AuthUnavailableError()
  }
  const tokens = (await res.json()) as AuthTokenResponse
  setTokens(tokens.access_token, tokens.refresh_token, getRememberMe())
  return tokens.access_token
}

export async function refreshAccessToken(): Promise<string> {
  if (inFlight) return inFlight
  inFlight = doRefresh().finally(() => {
    inFlight = null
  })
  return inFlight
}

export async function ensureValidToken(): Promise<string> {
  return refreshAccessToken()
}

export async function proactiveRefresh(
  currentToken: string | null,
  url: string,
): Promise<string | null> {
  if (url.includes(AUTH_ENDPOINT_PREFIX)) return currentToken
  if (currentToken && !isTokenExpired(currentToken)) return currentToken
  if (!getRefreshToken()) return currentToken
  try {
    return await refreshAccessToken()
  } catch (error) {
    if (error instanceof AuthUnavailableError) return currentToken
    throw error
  }
}

export async function reactiveRefresh(): Promise<string> {
  return refreshAccessToken()
}

export function forceLogout(): void {
  clearTokens()
  window.location.href = '/login'
}
