import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, Loader2, Mail, RefreshCw } from 'lucide-react'
import { REGEXP_ONLY_DIGITS } from 'input-otp'

import { Button } from '@/components/ui/button'
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from '@/components/ui/input-otp'

const RESEND_COOLDOWN_SECONDS = 30
const CODE_LENGTH = 6

type Props = {
  email: string
  isVerified?: boolean
  isSending?: boolean
  isVerifying?: boolean
  error?: string | null
  onVerify: (code: string) => void
  onResend: () => void
  onBack?: () => void
}

export function OtpForm({
  email,
  isVerified = false,
  isSending = false,
  isVerifying = false,
  error = null,
  onVerify,
  onResend,
  onBack,
}: Props) {
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS)
  const [code, setCode] = useState('')

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => setCooldown((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  const handleResend = useCallback(() => {
    onResend()
    setCode('')
    setCooldown(RESEND_COOLDOWN_SECONDS)
  }, [onResend])

  function handleCodeChange(value: string) {
    setCode(value)
    if (value.length === CODE_LENGTH) onVerify(value)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-5 rounded-lg border bg-card px-6 py-10 text-center">
        <div className="rounded-full bg-primary/10 p-3">
          {isVerified ? (
            <CheckCircle2 className="size-8 text-primary" />
          ) : (
            <Mail className="size-8 text-primary" />
          )}
        </div>

        {isVerified ? (
          <div className="space-y-1.5">
            <p className="text-base font-semibold">Signed in</p>
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{email}</span> —
              redirecting…
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
              <p className="text-base font-semibold">Enter verification code</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                We sent a 6-digit code to{' '}
                <span className="font-medium text-foreground">{email}</span>. It
                expires in 10 minutes.
              </p>
            </div>

            <InputOTP
              maxLength={CODE_LENGTH}
              value={code}
              onChange={handleCodeChange}
              disabled={isVerifying}
              pattern={REGEXP_ONLY_DIGITS}
              autoFocus
            >
              <InputOTPGroup>
                <InputOTPSlot index={0} />
                <InputOTPSlot index={1} />
                <InputOTPSlot index={2} />
              </InputOTPGroup>
              <InputOTPSeparator />
              <InputOTPGroup>
                <InputOTPSlot index={3} />
                <InputOTPSlot index={4} />
                <InputOTPSlot index={5} />
              </InputOTPGroup>
            </InputOTP>

            {isVerifying ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Verifying…
              </div>
            ) : null}
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}

            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSending || cooldown > 0}
              onClick={handleResend}
            >
              {isSending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
            </Button>
            <p className="text-xs text-muted-foreground">
              Didn’t receive it? Check spam.
            </p>
          </>
        )}
      </div>

      {onBack && !isVerified ? (
        <Button type="button" variant="outline" onClick={onBack}>
          <ArrowLeft className="size-4" />
          Use a different email
        </Button>
      ) : null}
    </div>
  )
}
