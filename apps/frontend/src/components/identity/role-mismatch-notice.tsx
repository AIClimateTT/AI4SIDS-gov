import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel, isAdmin, isDmuWorkspace, type Identity } from '@/lib/identity'

const ROLE_NAMES = {
  corp: 'a regional corporation',
  dmu: 'the DMU',
  admin: 'a DMU administrator',
} as const

type ExpectedRole = keyof typeof ROLE_NAMES

function matchesExpected(identity: Identity, expected: ExpectedRole): boolean {
  if (expected === 'corp') return identity.role === 'corp'
  if (expected === 'admin') return isAdmin(identity)
  return isDmuWorkspace(identity)
}

/**
 * Shown when the page belongs to a role the signed-in account does not have.
 */
export function RoleMismatchNotice({ expected }: { expected: ExpectedRole }) {
  const { identity } = useIdentity()
  const navigate = useNavigate()

  if (identity === null || matchesExpected(identity, expected)) return null

  return (
    <div className="rounded-md border border-dashed p-4 text-sm">
      <p>
        You are signed in as <strong>{identityLabel(identity)}</strong>, but this
        page belongs to {ROLE_NAMES[expected]}.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-3"
        onClick={() => void navigate({ to: '/' })}
      >
        Go to your home
      </Button>
    </div>
  )
}
