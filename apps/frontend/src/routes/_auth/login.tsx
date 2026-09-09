import { createFileRoute } from '@tanstack/react-router'

import { OtpLoginForm } from '@/features/auth/components/otp-login-form'

type LoginSearch = {
  redirect?: string
}

export const Route = createFileRoute('/_auth/login')({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
  }),
  component: LoginPage,
})

function LoginPage() {
  const { redirect } = Route.useSearch()
  return <OtpLoginForm redirect={redirect} />
}
