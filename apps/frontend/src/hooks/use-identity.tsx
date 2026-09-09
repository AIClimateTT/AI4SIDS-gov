import { createContext, useContext, type ReactNode } from 'react'

import { useOptionalAuth } from '@/lib/auth/auth-context'
import { sessionToIdentity, type Identity } from '@/lib/identity'

type IdentityContextValue = {
  identity: Identity | null
  forgetIdentity: () => Promise<void> | void
}

const IdentityOverrideContext = createContext<Identity | null | undefined>(
  undefined,
)

/**
 * Optional override for tests. Production identity is always derived from
 * the auth session — there is no client-side role switcher.
 */
export function IdentityProvider({
  children,
  identity,
}: {
  children: ReactNode
  identity?: Identity | null
}) {
  return (
    <IdentityOverrideContext value={identity}>
      {children}
    </IdentityOverrideContext>
  )
}

export function useIdentity(): IdentityContextValue {
  const override = useContext(IdentityOverrideContext)
  const auth = useOptionalAuth()
  const identity =
    override !== undefined ? override : sessionToIdentity(auth?.session ?? null)

  return {
    identity,
    forgetIdentity: auth?.logout ?? (() => undefined),
  }
}
