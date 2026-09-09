import { useEffect, useState } from 'react'
import { createFileRoute, useNavigate, useRouter } from '@tanstack/react-router'

import { OtpForm } from '@/features/auth/components/otp-form'
import { useAuth } from '@/lib/auth/auth-context'
import { OTP_EMAIL_KEY, OTP_REDIRECT_KEY } from '@/lib/auth/constants'

export const Route = createFileRoute('/_auth/verify')({
  component: VerifyPage,
})

function VerifyPage() {
  const router = useRouter()
  const navigate = useNavigate()
  const { verifyOtp, requestOtp } = useAuth()
  const email =
    typeof window === 'undefined'
      ? ''
      : (sessionStorage.getItem(OTP_EMAIL_KEY) ?? '')
  const [error, setError] = useState<string | null>(null)
  const [isVerifying, setIsVerifying] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isVerified, setIsVerified] = useState(false)

  useEffect(() => {
    if (!email) void navigate({ to: '/login' })
  }, [email, navigate])

  async function handleVerify(code: string) {
    setIsVerifying(true)
    setError(null)
    try {
      await verifyOtp(email, code, true)
      sessionStorage.removeItem(OTP_EMAIL_KEY)
      setIsVerified(true)
      await router.invalidate()
      const next = sessionStorage.getItem(OTP_REDIRECT_KEY) ?? '/'
      sessionStorage.removeItem(OTP_REDIRECT_KEY)
      setTimeout(() => router.history.push(next), 600)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid or expired code')
    } finally {
      setIsVerifying(false)
    }
  }

  async function handleResend() {
    setIsSending(true)
    setError(null)
    try {
      await requestOtp(email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend')
    } finally {
      setIsSending(false)
    }
  }

  if (!email) return null

  return (
    <OtpForm
      email={email}
      isVerified={isVerified}
      isSending={isSending}
      isVerifying={isVerifying}
      error={error}
      onVerify={handleVerify}
      onResend={handleResend}
      onBack={() => void navigate({ to: '/login' })}
    />
  )
}
