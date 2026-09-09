import {
  ACCESS_TOKEN_KEY,
  AUTH_CHANGE_EVENT,
  REFRESH_TOKEN_KEY,
  STORAGE_PREF_KEY,
  STORED_AT_KEY,
  TIMED_SESSION_MAX_AGE_MS,
} from '@/lib/auth/constants'

function emitAuthChange(): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT))
}

function timedSessionExpired(): boolean {
  if (typeof window === 'undefined') return true
  const pref = localStorage.getItem(STORAGE_PREF_KEY)
  if (pref !== 'timed') return false
  const storedAt = Number(localStorage.getItem(STORED_AT_KEY) ?? 0)
  if (!storedAt) return true
  return Date.now() - storedAt > TIMED_SESSION_MAX_AGE_MS
}

export function setTokens(
  accessToken: string,
  refreshToken: string,
  rememberMe: boolean,
): void {
  clearTokens()
  localStorage.setItem(STORAGE_PREF_KEY, rememberMe ? 'permanent' : 'timed')
  localStorage.setItem(STORED_AT_KEY, String(Date.now()))
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  emitAuthChange()
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    if (timedSessionExpired()) {
      clearTokens()
      return null
    }
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  } catch {
    return null
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    if (timedSessionExpired()) {
      clearTokens()
      return null
    }
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  } catch {
    return null
  }
}

export function getRememberMe(): boolean {
  if (typeof window === 'undefined') return true
  return localStorage.getItem(STORAGE_PREF_KEY) !== 'timed'
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(STORAGE_PREF_KEY)
    localStorage.removeItem(STORED_AT_KEY)
  } catch {
    // Safari private mode can throw; the in-memory session still clears.
  }
  emitAuthChange()
}
