import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'

/**
 * The corp-only gate block: RoleMismatchNotice plus an explanatory line.
 * Every corp-facing page renders this when the declared identity is not a
 * corporation, so it lives here once instead of being copy-pasted per page.
 */
export function CorpRoleNotice({ description }: { description: string }) {
  return (
    <div className="space-y-6">
      <RoleMismatchNotice expected="corp" />
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
