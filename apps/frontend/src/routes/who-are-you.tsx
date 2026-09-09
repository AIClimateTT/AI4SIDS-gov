import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/who-are-you')({
  beforeLoad: () => {
    throw redirect({ to: '/login' })
  },
})
