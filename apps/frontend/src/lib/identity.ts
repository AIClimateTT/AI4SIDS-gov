import {
  CANONICAL_CORPORATIONS,
  CORPORATION_LABELS,
  type CanonicalCorporation,
} from '@/lib/corporations'

export const IDENTITY_STORAGE_KEY = 'dmcu.identity'

/**
 * Who the operator says they are. This is a declaration, not a credential —
 * there is no authentication in this system and nothing here enforces access.
 */
export type Identity =
  | { role: 'dmu' }
  | { role: 'corp'; corporation: CanonicalCorporation }

/** The slice of the Storage API we use, injected so this is testable without a DOM. */
export type IdentityStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function isCanonicalCorporation(value: unknown): value is CanonicalCorporation {
  return (
    typeof value === 'string' &&
    (CANONICAL_CORPORATIONS as readonly string[]).includes(value)
  )
}

export function parseIdentity(raw: string | null): Identity | null {
  if (!raw) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return null
  }

  const value = parsed as Record<string, unknown>
  if (value.role === 'dmu') return { role: 'dmu' }
  if (value.role === 'corp' && isCanonicalCorporation(value.corporation)) {
    return { role: 'corp', corporation: value.corporation }
  }
  return null
}

export function serializeIdentity(identity: Identity): string {
  return JSON.stringify(identity)
}

export function loadIdentity(storage: IdentityStorage): Identity | null {
  try {
    return parseIdentity(storage.getItem(IDENTITY_STORAGE_KEY))
  } catch {
    // Safari private mode throws on access. No identity is a valid state;
    // a thrown error here would blank the app on first paint.
    return null
  }
}

export function saveIdentity(storage: IdentityStorage, identity: Identity): void {
  try {
    storage.setItem(IDENTITY_STORAGE_KEY, serializeIdentity(identity))
  } catch {
    // The choice still applies for this session via React state; it just
    // will not survive a reload. Losing persistence beats crashing.
  }
}

export function clearIdentity(storage: IdentityStorage): void {
  try {
    storage.removeItem(IDENTITY_STORAGE_KEY)
  } catch {
    // See saveIdentity.
  }
}

export function identityLabel(identity: Identity): string {
  return identity.role === 'dmu'
    ? 'Disaster Management Coordinating Unit'
    : CORPORATION_LABELS[identity.corporation]
}

export function identityHomePath(identity: Identity): '/corp' | '/dmu' {
  return identity.role === 'corp' ? '/corp' : '/dmu'
}
