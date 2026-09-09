import { TOKEN_EXPIRY_BUFFER_SECONDS } from '@/lib/auth/constants'
import { getAccessToken } from '@/lib/auth/storage'
import type { JwtPayload } from '@/lib/auth/types'

export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const segment = token.split('.')[1]
    if (!segment) return null
    const base64 = segment.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(
      base64.length + ((4 - (base64.length % 4)) % 4),
      '=',
    )
    return JSON.parse(atob(padded)) as JwtPayload
  } catch {
    return null
  }
}

export function isTokenExpired(
  token: string,
  bufferSeconds = TOKEN_EXPIRY_BUFFER_SECONDS,
): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload?.exp) return true
  return Date.now() >= (payload.exp - bufferSeconds) * 1000
}

export function isAuthenticated(): boolean {
  const token = getAccessToken()
  return token !== null && !isTokenExpired(token)
}
