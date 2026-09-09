import { Link, createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/system-unavailable')({
  component: SystemUnavailablePage,
})

function SystemUnavailablePage() {
  return (
    <div className="mx-auto flex min-h-svh w-full max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-bold">Sign-in temporarily unavailable</h1>
      <p className="text-sm text-muted-foreground">
        We couldn’t reach the authentication service. Your session has not been
        signed out. Try again in a moment.
      </p>
      <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
        Back to home
      </Link>
    </div>
  )
}
