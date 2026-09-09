import { redirect } from '@tanstack/react-router'

import { AuthUnavailableError, ensureValidToken } from '@/lib/auth/refresh'
import { isAuthenticated } from '@/lib/auth/token'

export async function requireAuth({
  location,
}: {
  location: { pathname: string; href?: string }
}) {
  if (isAuthenticated()) return
  try {
    await ensureValidToken()
  } catch (error) {
    if (error instanceof AuthUnavailableError) {
      throw redirect({ to: '/system-unavailable' })
    }
    throw redirect({
      to: '/login',
      search: { redirect: location.pathname ?? '/' },
    })
  }
}
