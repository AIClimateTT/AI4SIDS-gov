import { createFileRoute, redirect } from '@tanstack/react-router'

// Reports are created from a dialog on the list; this keeps old links working.
export const Route = createFileRoute('/dmu/reports/new')({
  beforeLoad: () => {
    throw redirect({ to: '/dmu/reports' })
  },
})
