import { useNavigate, useRouter } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'
import { queryClient } from '@/lib/query-client'

export function IdentityBadge() {
  const { identity, forgetIdentity } = useIdentity()
  const navigate = useNavigate()
  const router = useRouter()

  if (identity === null) return null

  return (
    <div className="ml-auto flex items-center gap-3">
      <span className="text-sm font-medium">{identityLabel(identity)}</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          void (async () => {
            await forgetIdentity()
            queryClient.clear()
            await router.invalidate()
            void navigate({ to: '/login' })
          })()
        }}
      >
        Sign out
      </Button>
    </div>
  )
}
