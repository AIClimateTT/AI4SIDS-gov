import { API_BASE_URL } from '@/lib/auth/constants'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '@/lib/auth/storage'
import { decodeJwtPayload } from '@/lib/auth/token'
import {
  mapPayloadToSession,
  type AuthTokenResponse,
  type Session,
} from '@/lib/auth/types'

function persistSession(tokens: AuthTokenResponse, rememberMe = true): Session {
  const payload = decodeJwtPayload(tokens.access_token)
  if (!payload) throw new Error('Invalid token payload')
  setTokens(tokens.access_token, tokens.refresh_token, rememberMe)
  return mapPayloadToSession(payload as Record<string, unknown>, tokens)
}

export function buildSessionFromTokenState(): Session | null {
  const accessToken = getAccessToken()
  const refreshToken = getRefreshToken()
  if (!accessToken || !refreshToken) return null
  const payload = decodeJwtPayload(accessToken)
  if (!payload) return null
  return mapPayloadToSession(payload as Record<string, unknown>, {
    access_token: accessToken,
    refresh_token: refreshToken,
  })
}

async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({}))
  return typeof err.detail === 'string' ? err.detail : fallback
}

export async function loginWithPassword(
  email: string,
  password: string,
  rememberMe = true,
): Promise<Session> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Invalid email or password'))
  }
  return persistSession((await res.json()) as AuthTokenResponse, rememberMe)
}

export async function requestOtp(email: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to send code'))
  }
}

export async function verifyOtpAndLogin(
  email: string,
  code: string,
  rememberMe = true,
): Promise<Session> {
  const res = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Invalid or expired code'))
  }
  return persistSession((await res.json()) as AuthTokenResponse, rememberMe)
}

export async function logoutCurrentSession(): Promise<void> {
  const refreshToken = getRefreshToken()
  if (refreshToken) {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
    } catch {
      // still clear locally
    }
  }
  clearTokens()
}
