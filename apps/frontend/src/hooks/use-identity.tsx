import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import {
  clearIdentity,
  loadIdentity,
  saveIdentity,
  type Identity,
  type IdentityStorage,
} from '@/lib/identity'

type IdentityContextValue = {
  identity: Identity | null
  setIdentity: (next: Identity) => void
  forgetIdentity: () => void
}

const IdentityContext = createContext<IdentityContextValue | null>(null)

const noopStorage: IdentityStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
}

function defaultStorage(): IdentityStorage {
  return typeof window === 'undefined' ? noopStorage : window.localStorage
}

export function IdentityProvider({
  children,
  storage,
}: {
  children: ReactNode
  storage?: IdentityStorage
}) {
  const resolved = useMemo(() => storage ?? defaultStorage(), [storage])
  const [identity, setIdentityState] = useState<Identity | null>(() =>
    loadIdentity(resolved),
  )

  const setIdentity = useCallback(
    (next: Identity) => {
      saveIdentity(resolved, next)
      setIdentityState(next)
    },
    [resolved],
  )

  const forgetIdentity = useCallback(() => {
    clearIdentity(resolved)
    setIdentityState(null)
  }, [resolved])

  const value = useMemo(
    () => ({ identity, setIdentity, forgetIdentity }),
    [identity, setIdentity, forgetIdentity],
  )

  return <IdentityContext value={value}>{children}</IdentityContext>
}

export function useIdentity(): IdentityContextValue {
  const value = useContext(IdentityContext)
  if (value === null) {
    throw new Error('useIdentity must be used inside an IdentityProvider')
  }
  return value
}
