import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'

/**
 * Always-visible statement of who the operator says they are, with a
 * frictionless switch. Deliberately plain: no lock, no avatar, no "sign out".
 * Dressing a declaration up as a session would imply a security boundary that
 * does not exist.
 */
export function IdentityBadge() {
  const { identity, forgetIdentity } = useIdentity()
  const navigate = useNavigate()

  if (identity === null) return null

  return (
    <div className="ml-auto flex items-center gap-3">
      <span className="text-sm font-medium">{identityLabel(identity)}</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          forgetIdentity()
          void navigate({ to: '/who-are-you' })
        }}
      >
        Switch
      </Button>
    </div>
  )
}
