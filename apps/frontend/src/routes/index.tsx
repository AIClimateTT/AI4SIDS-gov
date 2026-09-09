import { createFileRoute, redirect } from '@tanstack/react-router'

import { buildSessionFromTokenState } from '@/lib/auth/actions'
import { isAuthenticated } from '@/lib/auth/token'
import { identityHomePath, sessionToIdentity } from '@/lib/identity'

export const Route = createFileRoute('/')({
  beforeLoad: () => {
    if (typeof window === 'undefined' || !isAuthenticated()) {
      throw redirect({ to: '/login' })
    }
    const identity = sessionToIdentity(buildSessionFromTokenState())
    throw redirect({ to: identity ? identityHomePath(identity) : '/login' })
  },
})
