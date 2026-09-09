import { decodeJwtPayload } from '@/lib/auth/token'
import type { UserAccount } from '@/types/users'

export function userDisplayName(
  user: Pick<UserAccount, 'first_name' | 'last_name'>,
): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || '—'
}

export function currentUserIdFromToken(token: string | null): string | null {
  if (!token) return null
  return decodeJwtPayload(token)?.sub ?? null
}
