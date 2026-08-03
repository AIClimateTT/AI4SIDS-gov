import { createFileRoute, redirect } from '@tanstack/react-router'

import { identityHomePath, loadIdentity } from '@/lib/identity'

export const Route = createFileRoute('/')({
  // Reads storage directly rather than context: beforeLoad runs outside the
  // React tree. When real authentication arrives this reads a session instead
  // and no screen below it changes.
  beforeLoad: () => {
    const identity =
      typeof window === 'undefined' ? null : loadIdentity(window.localStorage)
    throw redirect({ to: identity ? identityHomePath(identity) : '/who-are-you' })
  },
})
