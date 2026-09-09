import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  buildSessionFromTokenState,
  logoutCurrentSession,
  requestOtp as requestOtpAction,
  verifyOtpAndLogin,
} from '@/lib/auth/actions'
import { AUTH_CHANGE_EVENT } from '@/lib/auth/constants'
import type { Session } from '@/lib/auth/types'

export interface AuthContextType {
  session: Session | null
  requestOtp: (email: string) => Promise<void>
  verifyOtp: (
    email: string,
    code: string,
    rememberMe?: boolean,
  ) => Promise<Session>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() =>
    buildSessionFromTokenState(),
  )

  useEffect(() => {
    const sync = () => setSession(buildSessionFromTokenState())
    window.addEventListener('storage', sync)
    window.addEventListener(AUTH_CHANGE_EVENT, sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(AUTH_CHANGE_EVENT, sync)
    }
  }, [])

  const requestOtp = useCallback(async (email: string) => {
    await requestOtpAction(email)
  }, [])

  const verifyOtp = useCallback(
    async (email: string, code: string, rememberMe = true) => {
      const next = await verifyOtpAndLogin(email, code, rememberMe)
      setSession(next)
      return next
    },
    [],
  )

  const logout = useCallback(async () => {
    await logoutCurrentSession()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, requestOtp, verifyOtp, logout }),
    [session, requestOtp, verifyOtp, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthContextType {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return value
}

export function useOptionalAuth(): AuthContextType | null {
  return useContext(AuthContext)
}
