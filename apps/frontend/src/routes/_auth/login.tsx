import { createFileRoute } from '@tanstack/react-router'

import { PasswordLoginForm } from '@/features/auth/components/password-login-form'

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
  return <PasswordLoginForm redirect={redirect} />
}
