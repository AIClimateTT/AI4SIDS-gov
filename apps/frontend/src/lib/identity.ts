import { CORPORATION_LABELS, isCanonicalCorporation } from '@/lib/corporations'
import type { CanonicalCorporation } from '@/lib/corporations'

/**
 * Who the signed-in operator is. Derived from the JWT session — not a
 * client-side declaration. Role and corporation come from the user record.
 */
export type Identity =
  { role: 'dmu' } | { role: 'corp'; corporation: CanonicalCorporation }

export function sessionToIdentity(
  session: { role: string; corporation?: string } | null,
): Identity | null {
  if (!session) return null
  if (session.role === 'dmu') return { role: 'dmu' }
  if (session.role === 'corp' && isCanonicalCorporation(session.corporation)) {
    return { role: 'corp', corporation: session.corporation }
  }
  return null
}

export function identityLabel(identity: Identity): string {
  return identity.role === 'dmu'
    ? 'Disaster Management Coordinating Unit'
    : CORPORATION_LABELS[identity.corporation]
}

export function identityHomePath(identity: Identity): '/corp' | '/dmu' {
  return identity.role === 'corp' ? '/corp' : '/dmu'
}
