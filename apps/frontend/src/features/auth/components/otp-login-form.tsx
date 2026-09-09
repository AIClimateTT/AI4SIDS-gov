import { useState } from 'react'
import { z } from 'zod'
import { useNavigate } from '@tanstack/react-router'

import { useAppForm } from '@/hooks/form'
import { useAuth } from '@/lib/auth/auth-context'
import { OTP_EMAIL_KEY, OTP_REDIRECT_KEY } from '@/lib/auth/constants'

const schema = z.object({ email: z.string().email('Invalid email address') })

export function OtpLoginForm({ redirect }: { redirect?: string }) {
  const navigate = useNavigate()
  const { requestOtp } = useAuth()
  const [error, setError] = useState<string | null>(null)

  const form = useAppForm({
    defaultValues: { email: '' },
    validators: { onChange: schema },
    onSubmit: async ({ value }) => {
      setError(null)
      try {
        await requestOtp(value.email)
        sessionStorage.setItem(OTP_EMAIL_KEY, value.email)
        if (redirect) sessionStorage.setItem(OTP_REDIRECT_KEY, redirect)
        void navigate({ to: '/verify' })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send code')
      }
    },
  })

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void form.handleSubmit()
      }}
    >
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          We’ll email you a 6-digit code. No password needed.
        </p>
      </div>
      <form.AppField name="email">
        {(field) => (
          <field.TextField
            label="Email"
            type="email"
            placeholder="you@example.com"
            required
          />
        )}
      </form.AppField>
      <form.AppForm>
        <form.SubmitButton label="Email me a code" className="w-full" />
      </form.AppForm>
      {error ? (
        <p className="text-center text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  )
}
