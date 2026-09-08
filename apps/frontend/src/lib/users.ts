import type { UserAccount } from '@/types/users'

export function userDisplayName(
  user: Pick<UserAccount, 'first_name' | 'last_name'>,
): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || '—'
}

export function currentUserIdFromToken(token: string | null): string | null {
  if (!token) return null
  try {
    const segment = token.split('.')[1]
    if (!segment) return null
    const padded = segment.replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(
      padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), '='),
    )
    const payload = JSON.parse(json) as { sub?: unknown }
    return typeof payload.sub === 'string' ? payload.sub : null
  } catch {
    return null
  }
}
