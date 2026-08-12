import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'

const ROLE_NAMES = {
  corp: 'a regional corporation',
  dmu: 'the DMU',
} as const

/**
 * Shown when the page belongs to a role the operator has not declared.
 *
 * This is an offer, not a block. There is no authentication here, so refusing
 * to render the page would be theatre — it would imply an enforced boundary
 * while the operator can switch roles in one click anyway. Say plainly what is
 * going on and make the switch easy.
 */
export function RoleMismatchNotice({ expected }: { expected: 'corp' | 'dmu' }) {
  const { identity } = useIdentity()
  const navigate = useNavigate()

  if (identity === null || identity.role === expected) return null

  return (
    <div className="rounded-md border border-dashed p-4 text-sm">
      <p>
        You are viewing as <strong>{identityLabel(identity)}</strong>, but this page
        belongs to {ROLE_NAMES[expected]}.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-3"
        onClick={() => void navigate({ to: '/who-are-you' })}
      >
        Switch
      </Button>
    </div>
  )
}
