import { useState } from 'react'
import { z } from 'zod'
import { useRouter } from '@tanstack/react-router'

import { useAppForm } from '@/hooks/form'
import { useAuth } from '@/lib/auth/auth-context'

const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

export function PasswordLoginForm({ redirect }: { redirect?: string }) {
  const router = useRouter()
  const { loginWithPassword } = useAuth()
  const [error, setError] = useState<string | null>(null)

  const form = useAppForm({
    defaultValues: { email: '', password: '' },
    validators: { onChange: schema },
    onSubmit: async ({ value }) => {
      setError(null)
      try {
        await loginWithPassword(value.email, value.password, true)
        await router.invalidate()
        router.history.push(redirect || '/')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Invalid email or password')
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
          Use the email and password given to you by an administrator.
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
      <form.AppField name="password">
        {(field) => (
          <field.TextField label="Password" type="password" required />
        )}
      </form.AppField>
      <form.AppForm>
        <form.SubmitButton label="Sign in" className="w-full" />
      </form.AppForm>
      {error ? (
        <p className="text-center text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  )
}
