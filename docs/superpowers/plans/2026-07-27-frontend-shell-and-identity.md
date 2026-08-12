# Frontend Shell and Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the app around two declared identities — a regional corporation or the DMU — so navigation, routes and context belong to whoever is using it, without introducing authentication.

**Architecture:** Identity is a plain value (`{ role: 'dmu' } | { role: 'corp', corporation }`) held in `localStorage`, read through pure parse/serialise functions and exposed to React via one context. Routes split into `/corp/*` and `/dmu/*`; `/` redirects to whichever identity is stored, or to a who-are-you screen. The existing admin surfaces move under `/dmu/admin` rather than being deleted.

**Tech Stack:** React 19, TanStack Router (file-based, `autoCodeSplitting`), TanStack Query, Tailwind 4, shadcn-style UI primitives, Vitest.

**Spec:** `docs/superpowers/specs/2026-07-27-corp-dmu-frontend-design.md`

## Global Constraints

- **No authentication, and nothing that impersonates it.** No lock icons, no "sign out", no password field, no route that returns 403. Identity is a declaration the user can change in one click. A cross-role URL shows an inline offer to switch, never a block.
- **Identity is `{ role: 'dmu' } | { role: 'corp'; corporation: CanonicalCorporation }`.** The corporation must be one of the fourteen in `src/lib/corporations.ts`; any other value is treated as no identity at all.
- **`localStorage` access must never throw into React.** Safari private mode throws on `getItem`/`setItem`. Every access is wrapped, and a failure degrades to "no identity", never a crash.
- **Storage is injected, not imported.** Functions that touch storage take an `IdentityStorage` parameter so they are testable without a DOM. Vitest currently runs in the default `node` environment — there is no `test` block in `vite.config.ts` and you must not add one.
- **Do not delete the admin surfaces.** Templates and Modules move to `/dmu/admin/*`. They are real tools for whoever configures the system.
- **Run the frontend from `apps/frontend`** with `pnpm`. Typecheck: `pnpm exec tsc --noEmit -p tsconfig.json`. Tests: `pnpm test`. Route tree regeneration: `pnpm generate-routes`.
- **`src/routeTree.gen.ts` is generated.** Never hand-edit it; regenerate it and commit the result.

---

## File Structure

**Create:**
- `src/lib/identity.ts` — identity type, pure parse/serialise, storage read/write, display helpers. No React.
- `src/lib/identity.test.ts` — Vitest coverage for the above.
- `src/hooks/use-identity.tsx` — `IdentityProvider` + `useIdentity()`.
- `src/components/identity/identity-badge.tsx` — the header display and switch control.
- `src/components/identity/role-mismatch-notice.tsx` — the inline cross-role offer.
- `src/routes/who-are-you.tsx` — the selection screen.
- `src/routes/corp/index.tsx`, `src/routes/dmu/index.tsx` — role landing pages.

**Move (git mv, then regenerate the route tree):**
- `src/routes/index.tsx` → `src/routes/dmu/index.tsx`
- `src/routes/ingest.tsx` → `src/routes/dmu/field-data.tsx`
- `src/routes/modules.tsx` → `src/routes/dmu/admin/modules.tsx`
- `src/routes/reports/*` → `src/routes/dmu/reports/*`
- `src/routes/templates/*` → `src/routes/dmu/admin/templates/*`

**Delete:**
- `src/routes/reports/corp.tsx` — it generates `single_region_report`, whose data requirements are Survey123-only, so a corp officer would receive a "region report" built from field observations rather than their own submission. Realignment plan 3 rebuilds this properly against corp data.

**Modify:**
- `src/routes/__root.tsx` — wrap in `IdentityProvider`, put the identity badge in the header.
- `src/components/app-sidebar.tsx` — role-shaped navigation.
- `src/lib/queries/*`, `src/lib/api/*` — untouched. This plan moves routes and adds context; it changes no data fetching.

---

## Task 1: Corporation display names and the identity module

**Files:**
- Modify: `apps/frontend/src/lib/corporations.ts`
- Create: `apps/frontend/src/lib/identity.ts`
- Test: `apps/frontend/src/lib/identity.test.ts`

**Why the display names change is here:** the canonical ids are truncated to 31 characters by the Survey123 export (`diego_martin_regional_corporati`), and `formatConstant` faithfully renders that truncation — so the app currently shows users **"Diego Martin Regional Corporati"**. Identity is about to put a corporation's name permanently in the header, so the truncation has to go first.

**Interfaces:**
- Consumes: `CANONICAL_CORPORATIONS`, `CanonicalCorporation` from `@/lib/corporations`.
- Also produces: `CORPORATION_LABELS: Record<CanonicalCorporation, string>` and a `CORPORATION_OPTIONS` that uses it.
- Produces:
  - `IDENTITY_STORAGE_KEY: string`
  - `type Identity = { role: 'dmu' } | { role: 'corp'; corporation: CanonicalCorporation }`
  - `type IdentityStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>`
  - `parseIdentity(raw: string | null): Identity | null`
  - `serializeIdentity(identity: Identity): string`
  - `loadIdentity(storage: IdentityStorage): Identity | null`
  - `saveIdentity(storage: IdentityStorage, identity: Identity): void`
  - `clearIdentity(storage: IdentityStorage): void`
  - `identityLabel(identity: Identity): string`
  - `identityHomePath(identity: Identity): '/corp' | '/dmu'`

- [ ] **Step 1: Add real corporation names**

In `apps/frontend/src/lib/corporations.ts`, add the label map below `CanonicalCorporation` and rewrite `CORPORATION_OPTIONS` to use it. Keep `CANONICAL_CORPORATIONS` exactly as it is — those strings are database keys and must not change. Names match the corporation headings in `docs/examples/Full Sitrep 2023.docx`.

```ts
/**
 * Proper names for display. The canonical ids are truncated to 31 characters by
 * the Survey123 export, so deriving a label from the id yields "Diego Martin
 * Regional Corporati". These strings are the only thing a user should ever see.
 */
export const CORPORATION_LABELS: Record<CanonicalCorporation, string> = {
  san_juan_laventille_regional_co: 'San Juan/Laventille Regional Corporation',
  tunapuna_piarco_regional_corpor: 'Tunapuna/Piarco Regional Corporation',
  sangre_grande_regional_corporat: 'Sangre Grande Regional Corporation',
  penal_debe_regional_corporation: 'Penal/Debe Regional Corporation',
  couva_tabaquite_talparo_regiona: 'Couva/Tabaquite/Talparo Regional Corporation',
  mayaro_rio_claro_regional_corpo: 'Mayaro/Rio Claro Regional Corporation',
  siparia_regional_corporation: 'Siparia Regional Corporation',
  princes_town_regional_corporati: 'Princes Town Regional Corporation',
  diego_martin_regional_corporati: 'Diego Martin Regional Corporation',
  san_fernando_city_corporation: 'San Fernando City Corporation',
  chaguanas_borough_corporation: 'Chaguanas Borough Corporation',
  port_of_spain_city_corporation: 'Port of Spain City Corporation',
  point_fortin_borough_corporatio: 'Point Fortin Borough Corporation',
  arima_borough_corporation: 'Arima Borough Corporation',
}

export const CORPORATION_OPTIONS: CorporationOption[] = CANONICAL_CORPORATIONS.map(
  (value) => ({ value, label: CORPORATION_LABELS[value] }),
).sort((a, b) => a.label.localeCompare(b.label))
```

Delete the now-unused `formatConstant` import from this file if nothing else in it uses it. Because the map is typed `Record<CanonicalCorporation, string>`, adding a corporation to `CANONICAL_CORPORATIONS` without a label becomes a compile error rather than a silent truncation.

- [ ] **Step 2: Write the failing test**

Create `apps/frontend/src/lib/identity.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import { CANONICAL_CORPORATIONS } from '@/lib/corporations'
import {
  IDENTITY_STORAGE_KEY,
  clearIdentity,
  identityHomePath,
  identityLabel,
  loadIdentity,
  parseIdentity,
  saveIdentity,
  serializeIdentity,
  type Identity,
  type IdentityStorage,
} from '@/lib/identity'

const DIEGO_MARTIN = 'diego_martin_regional_corporati'

function fakeStorage(initial: Record<string, string> = {}): IdentityStorage & {
  values: Record<string, string>
} {
  const values = { ...initial }
  return {
    values,
    getItem: (key: string) => (key in values ? values[key] : null),
    setItem: (key: string, value: string) => {
      values[key] = value
    },
    removeItem: (key: string) => {
      delete values[key]
    },
  }
}

function throwingStorage(): IdentityStorage {
  return {
    getItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
    setItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
    removeItem: () => {
      throw new Error('SecurityError: localStorage is unavailable')
    },
  }
}

describe('parseIdentity', () => {
  it('accepts the DMU role', () => {
    expect(parseIdentity('{"role":"dmu"}')).toEqual({ role: 'dmu' })
  })

  it('accepts a corp role with a canonical corporation', () => {
    expect(parseIdentity(`{"role":"corp","corporation":"${DIEGO_MARTIN}"}`)).toEqual({
      role: 'corp',
      corporation: DIEGO_MARTIN,
    })
  })

  it('rejects a corporation that is not one of the fourteen', () => {
    expect(parseIdentity('{"role":"corp","corporation":"atlantis_city_corporation"}')).toBeNull()
  })

  it('rejects a corp role with no corporation', () => {
    expect(parseIdentity('{"role":"corp"}')).toBeNull()
  })

  it('rejects an unknown role', () => {
    expect(parseIdentity('{"role":"minister"}')).toBeNull()
  })

  it('returns null for null, empty, malformed and non-object input', () => {
    expect(parseIdentity(null)).toBeNull()
    expect(parseIdentity('')).toBeNull()
    expect(parseIdentity('not json at all')).toBeNull()
    expect(parseIdentity('"a string"')).toBeNull()
    expect(parseIdentity('null')).toBeNull()
    expect(parseIdentity('[]')).toBeNull()
  })
})

describe('round trip', () => {
  it('survives serialize then parse for both roles', () => {
    const dmu: Identity = { role: 'dmu' }
    const corp: Identity = { role: 'corp', corporation: DIEGO_MARTIN }

    expect(parseIdentity(serializeIdentity(dmu))).toEqual(dmu)
    expect(parseIdentity(serializeIdentity(corp))).toEqual(corp)
  })
})

describe('storage', () => {
  it('saves under the shared key and loads it back', () => {
    const storage = fakeStorage()
    const identity: Identity = { role: 'corp', corporation: DIEGO_MARTIN }

    saveIdentity(storage, identity)

    expect(storage.values[IDENTITY_STORAGE_KEY]).toBe(serializeIdentity(identity))
    expect(loadIdentity(storage)).toEqual(identity)
  })

  it('loads null when nothing is stored', () => {
    expect(loadIdentity(fakeStorage())).toBeNull()
  })

  it('loads null when the stored value is corrupt, rather than throwing', () => {
    const storage = fakeStorage({ [IDENTITY_STORAGE_KEY]: '{oh no' })

    expect(loadIdentity(storage)).toBeNull()
  })

  it('clears the stored identity', () => {
    const storage = fakeStorage()
    saveIdentity(storage, { role: 'dmu' })

    clearIdentity(storage)

    expect(loadIdentity(storage)).toBeNull()
  })

  it('degrades to no identity when storage itself throws', () => {
    // Safari in private mode throws on access. A crash here would take the
    // whole app down on first paint, so every access is wrapped.
    const storage = throwingStorage()

    expect(loadIdentity(storage)).toBeNull()
    expect(() => saveIdentity(storage, { role: 'dmu' })).not.toThrow()
    expect(() => clearIdentity(storage)).not.toThrow()
  })
})

describe('display helpers', () => {
  it('labels the DMU with its full name', () => {
    expect(identityLabel({ role: 'dmu' })).toBe('Disaster Management Coordinating Unit')
  })

  it('labels a corporation with its full untruncated name', () => {
    // Guards the truncation: deriving this from the id would yield
    // "Diego Martin Regional Corporati".
    expect(identityLabel({ role: 'corp', corporation: DIEGO_MARTIN })).toBe(
      'Diego Martin Regional Corporation',
    )
  })

  it('has a label for every canonical corporation', () => {
    for (const corporation of CANONICAL_CORPORATIONS) {
      const label = identityLabel({ role: 'corp', corporation })
      expect(label).toBeTruthy()
      expect(label).not.toMatch(/Corporati$/)
    }
  })

  it('routes each role to its own home', () => {
    expect(identityHomePath({ role: 'dmu' })).toBe('/dmu')
    expect(identityHomePath({ role: 'corp', corporation: DIEGO_MARTIN })).toBe('/corp')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/frontend && pnpm test src/lib/identity.test.ts`
Expected: FAIL — cannot resolve `@/lib/identity`.

- [ ] **Step 4: Write the module**

Create `apps/frontend/src/lib/identity.ts`:

```ts
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/frontend && pnpm test src/lib/identity.test.ts`
Expected: PASS (16 tests)

- [ ] **Step 6: Typecheck and run the whole suite**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json && pnpm test`
Expected: `tsc` silent; suite passes (16 new plus the 3 pre-existing `format-constant` tests).

- [ ] **Step 7: Commit**

```bash
cd apps/frontend
git add src/lib/corporations.ts src/lib/identity.ts src/lib/identity.test.ts
git commit -m "frontend: add identity module and untruncated corporation names"
```

---

## Task 2: Identity context and header badge

**Files:**
- Create: `apps/frontend/src/hooks/use-identity.tsx`
- Create: `apps/frontend/src/components/identity/identity-badge.tsx`
- Modify: `apps/frontend/src/routes/__root.tsx`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces:
  - `IdentityProvider({ children, storage? }: { children: ReactNode; storage?: IdentityStorage })`
  - `useIdentity(): { identity: Identity | null; setIdentity: (next: Identity) => void; forgetIdentity: () => void }`
  - `<IdentityBadge />`

- [ ] **Step 1: Write the context**

Create `apps/frontend/src/hooks/use-identity.tsx`:

```tsx
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import {
  clearIdentity,
  loadIdentity,
  saveIdentity,
  type Identity,
  type IdentityStorage,
} from '@/lib/identity'

type IdentityContextValue = {
  identity: Identity | null
  setIdentity: (next: Identity) => void
  forgetIdentity: () => void
}

const IdentityContext = createContext<IdentityContextValue | null>(null)

const noopStorage: IdentityStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
}

function defaultStorage(): IdentityStorage {
  return typeof window === 'undefined' ? noopStorage : window.localStorage
}

export function IdentityProvider({
  children,
  storage,
}: {
  children: ReactNode
  storage?: IdentityStorage
}) {
  const resolved = useMemo(() => storage ?? defaultStorage(), [storage])
  const [identity, setIdentityState] = useState<Identity | null>(() =>
    loadIdentity(resolved),
  )

  const setIdentity = useCallback(
    (next: Identity) => {
      saveIdentity(resolved, next)
      setIdentityState(next)
    },
    [resolved],
  )

  const forgetIdentity = useCallback(() => {
    clearIdentity(resolved)
    setIdentityState(null)
  }, [resolved])

  const value = useMemo(
    () => ({ identity, setIdentity, forgetIdentity }),
    [identity, setIdentity, forgetIdentity],
  )

  return <IdentityContext value={value}>{children}</IdentityContext>
}

export function useIdentity(): IdentityContextValue {
  const value = useContext(IdentityContext)
  if (value === null) {
    throw new Error('useIdentity must be used inside an IdentityProvider')
  }
  return value
}
```

- [ ] **Step 2: Write the header badge**

Create `apps/frontend/src/components/identity/identity-badge.tsx`:

```tsx
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
```

- [ ] **Step 3: Wire both into the root route**

In `apps/frontend/src/routes/__root.tsx`, add the imports:

```tsx
import { IdentityBadge } from '@/components/identity/identity-badge'
import { IdentityProvider } from '@/hooks/use-identity'
```

Wrap the existing `<TooltipProvider>` tree in `<IdentityProvider>` so it is the outermost provider, and replace the header's static paragraph with the badge alongside it:

```tsx
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <p className="text-sm text-muted-foreground">
              Disaster Management Coordinating Unit
            </p>
            <IdentityBadge />
          </header>
```

- [ ] **Step 4: Typecheck and build**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json && pnpm build`
Expected: both succeed.

- [ ] **Step 5: Run the existing suite**

Run: `cd apps/frontend && pnpm test`
Expected: PASS — Task 1's 16 tests plus the 3 pre-existing `format-constant` tests.

- [ ] **Step 6: Commit**

```bash
cd apps/frontend
git add src/hooks/use-identity.tsx src/components/identity/identity-badge.tsx src/routes/__root.tsx
git commit -m "frontend: hold identity in context and show it in the header"
```

---

## Task 3: Who-are-you screen and root redirect

**Files:**
- Create: `apps/frontend/src/routes/who-are-you.tsx`
- Modify: `apps/frontend/src/routes/index.tsx`

**Interfaces:**
- Consumes: `useIdentity` (Task 2); `loadIdentity`, `identityHomePath` (Task 1); `CORPORATION_OPTIONS` from `@/lib/corporations`.
- Produces: the `/who-are-you` route, and `/` as a redirect-only route.

Note on ordering: at this point `/corp` and `/dmu` do not exist yet — Task 4 creates them. Between this task and Task 4 the redirect will land on a 404 for a stored identity. That is expected and is why these two tasks land back to back.

- [ ] **Step 1: Write the selection screen**

Create `apps/frontend/src/routes/who-are-you.tsx`:

```tsx
import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { ContentCard } from '@/components/shared/content-card'
import { PageHeader } from '@/components/shared'
import { useIdentity } from '@/hooks/use-identity'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { identityHomePath } from '@/lib/identity'
import type { CanonicalCorporation } from '@/lib/corporations'

export const Route = createFileRoute('/who-are-you')({
  component: WhoAreYouPage,
})

function WhoAreYouPage() {
  const { setIdentity } = useIdentity()
  const navigate = useNavigate()

  const choose = (
    identity:
      | { role: 'dmu' }
      | { role: 'corp'; corporation: CanonicalCorporation },
  ) => {
    setIdentity(identity)
    void navigate({ to: identityHomePath(identity) })
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader
        title="Who are you?"
        description="Choose where you work. You can change this at any time from the header."
      />

      <ContentCard
        title="Disaster Management Coordinating Unit"
        description="Review what corporations have reported and produce the ministerial situation report."
      >
        <Button onClick={() => choose({ role: 'dmu' })}>Continue as the DMU</Button>
      </ContentCard>

      <ContentCard
        title="Regional corporation"
        description="File your situation reports and manage your events."
      >
        <div className="grid gap-2 sm:grid-cols-2">
          {CORPORATION_OPTIONS.map((option) => (
            <Button
              key={option.value}
              variant="outline"
              className="justify-start"
              onClick={() => choose({ role: 'corp', corporation: option.value })}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </ContentCard>
    </div>
  )
}
```

- [ ] **Step 2: Turn `/` into a redirect**

Replace the entire contents of `apps/frontend/src/routes/index.tsx`. Its previous dashboard content moves to `/dmu` in Task 4 — do not delete that content, `git mv` it there.

```tsx
import { createFileRoute, redirect } from '@tanstack/react-router'

import { identityHomePath, loadIdentity } from '@/lib/identity'

export const Route = createFileRoute('/')({
  // Reads storage directly rather than context: beforeLoad runs outside the
  // React tree. When real authentication arrives this reads a session instead
  // and no screen below it changes.
  beforeLoad: () => {
    const identity =
      typeof window === 'undefined' ? null : loadIdentity(window.localStorage)
    throw redirect({ to: identity ? identityHomePath(identity) : '/who-are-you' })
  },
})
```

- [ ] **Step 3: Regenerate the route tree**

Run: `cd apps/frontend && pnpm generate-routes`
Expected: `src/routeTree.gen.ts` updates to include `/who-are-you`.

- [ ] **Step 4: Typecheck**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json`
Expected: errors on `/corp` and `/dmu` not existing as routes yet. Note them and continue — Task 4 creates them. If there are errors of any *other* kind, fix them before committing.

- [ ] **Step 5: Commit**

```bash
cd apps/frontend
git add src/routes/who-are-you.tsx src/routes/index.tsx src/routeTree.gen.ts
git commit -m "frontend: add the who-are-you screen and redirect the root by identity"
```

---

## Task 4: Split routes into /corp and /dmu

**Files:**
- Move: `src/routes/index.tsx`'s previous dashboard content → `src/routes/dmu/index.tsx`
- Move: `src/routes/ingest.tsx` → `src/routes/dmu/field-data.tsx`
- Move: `src/routes/modules.tsx` → `src/routes/dmu/admin/modules.tsx`
- Move: `src/routes/reports/{index,new,$reportId}.tsx` → `src/routes/dmu/reports/`
- Move: `src/routes/templates/**` → `src/routes/dmu/admin/templates/`
- Delete: `src/routes/reports/corp.tsx`
- Create: `src/routes/corp/index.tsx`
- Modify: every moved file's `createFileRoute` path string and any internal `<Link to=...>`

**Interfaces:**
- Consumes: nothing new.
- Produces: routes `/corp`, `/dmu`, `/dmu/field-data`, `/dmu/reports`, `/dmu/reports/new`, `/dmu/reports/$reportId`, `/dmu/admin/modules`, `/dmu/admin/templates`, `/dmu/admin/templates/$name`, `/dmu/admin/templates/$name/new`, `/dmu/admin/templates/$name/versions/$version`.

- [ ] **Step 1: Recover the dashboard and move the route files**

`git show HEAD~1:apps/frontend/src/routes/index.tsx` is the dashboard content replaced in Task 3. Write it to `src/routes/dmu/index.tsx`, then move the rest:

```bash
cd apps/frontend
mkdir -p src/routes/corp src/routes/dmu/reports src/routes/dmu/admin/templates
git show HEAD~1:apps/frontend/src/routes/index.tsx > src/routes/dmu/index.tsx
git mv src/routes/ingest.tsx src/routes/dmu/field-data.tsx
git mv src/routes/modules.tsx src/routes/dmu/admin/modules.tsx
git mv src/routes/reports/index.tsx src/routes/dmu/reports/index.tsx
git mv src/routes/reports/new.tsx src/routes/dmu/reports/new.tsx
git mv 'src/routes/reports/$reportId.tsx' 'src/routes/dmu/reports/$reportId.tsx'
git mv src/routes/templates/index.tsx src/routes/dmu/admin/templates/index.tsx
git mv 'src/routes/templates/$name' 'src/routes/dmu/admin/templates/$name'
git rm src/routes/reports/corp.tsx
git add src/routes/dmu/index.tsx
```

- [ ] **Step 2: Update every moved file's route path**

Each moved file declares its own path. Update the string in `createFileRoute(...)` to match its new location, exactly:

| File | New `createFileRoute` path |
|---|---|
| `src/routes/dmu/index.tsx` | `'/dmu/'` |
| `src/routes/dmu/field-data.tsx` | `'/dmu/field-data'` |
| `src/routes/dmu/admin/modules.tsx` | `'/dmu/admin/modules'` |
| `src/routes/dmu/reports/index.tsx` | `'/dmu/reports/'` |
| `src/routes/dmu/reports/new.tsx` | `'/dmu/reports/new'` |
| `src/routes/dmu/reports/$reportId.tsx` | `'/dmu/reports/$reportId'` |
| `src/routes/dmu/admin/templates/index.tsx` | `'/dmu/admin/templates/'` |
| `src/routes/dmu/admin/templates/$name/index.tsx` | `'/dmu/admin/templates/$name/'` |
| `src/routes/dmu/admin/templates/$name/new.tsx` | `'/dmu/admin/templates/$name/new'` |
| `src/routes/dmu/admin/templates/$name/versions/$version.tsx` | `'/dmu/admin/templates/$name/versions/$version'` |

- [ ] **Step 3: Update every internal link**

Find them all:

```bash
cd apps/frontend && grep -rn "to=\"/" src --include=*.tsx
```

Rewrite each `to` prop to its new path — `/reports` → `/dmu/reports`, `/reports/$reportId` → `/dmu/reports/$reportId`, `/templates` → `/dmu/admin/templates`, `/ingest` → `/dmu/field-data`, `/modules` → `/dmu/admin/modules`, and `/` → `/dmu` where a page links to the dashboard. Any link to `/reports/corp` is removed along with its button — that route no longer exists.

- [ ] **Step 4: Create the corp landing page**

Create `apps/frontend/src/routes/corp/index.tsx`. Events and filing arrive in a later plan; this establishes the route and says so honestly rather than rendering a blank page:

```tsx
import { createFileRoute } from '@tanstack/react-router'

import { EmptyState, PageHeader } from '@/components/shared'

export const Route = createFileRoute('/corp/')({
  component: CorpHomePage,
})

function CorpHomePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="My corporation"
        description="File situation reports and manage your events."
      />
      <EmptyState
        title="Nothing here yet"
        description="Events and report filing arrive in the next release. Your submissions will appear on this page."
      />
    </div>
  )
}
```

- [ ] **Step 5: Regenerate, typecheck, build**

```bash
cd apps/frontend
pnpm generate-routes
pnpm exec tsc --noEmit -p tsconfig.json
pnpm build
```
Expected: all three succeed with no output from `tsc`. A remaining error naming an old path means a link in Step 3 was missed.

- [ ] **Step 6: Run the suite**

Run: `cd apps/frontend && pnpm test`
Expected: PASS (19 tests).

- [ ] **Step 7: Commit**

```bash
cd apps/frontend
git add -A src/routes src/routeTree.gen.ts
git commit -m "frontend: split routes into /corp and /dmu, demote admin surfaces"
```

---

## Task 5: Role-shaped navigation

**Files:**
- Modify: `apps/frontend/src/components/app-sidebar.tsx`

**Interfaces:**
- Consumes: `useIdentity` (Task 2); the routes from Task 4.
- Produces: navigation that renders per role.

- [ ] **Step 1: Replace the flat nav with two role-specific sets**

In `apps/frontend/src/components/app-sidebar.tsx`, replace the single `navItems` array with:

```tsx
const CORP_NAV = [
  { title: 'Events', to: '/corp', icon: CalendarIcon },
] as const

const DMU_NAV = [
  { title: 'Dashboard', to: '/dmu', icon: LayoutDashboardIcon },
  { title: 'Field data', to: '/dmu/field-data', icon: UploadIcon },
  { title: 'Reports', to: '/dmu/reports', icon: FileTextIcon },
  { title: 'Templates', to: '/dmu/admin/templates', icon: LibraryIcon },
  { title: 'Modules', to: '/dmu/admin/modules', icon: BoxesIcon },
] as const
```

Import `CalendarIcon` from `lucide-react` alongside the existing icons, and drop `Building2Icon` if nothing else uses it.

Then, inside `AppSidebar`, select the set:

```tsx
  const { identity } = useIdentity()
  const navItems =
    identity === null ? [] : identity.role === 'corp' ? CORP_NAV : DMU_NAV
```

Render `navItems` exactly as the existing markup does. With no identity the sidebar is empty, which is correct — the only page reachable in that state is the who-are-you screen.

The corp nav is deliberately one item at this stage. "File a report" and "My submissions" arrive with the screens they point at; adding dead links now would be worse than a short menu.

- [ ] **Step 2: Typecheck and build**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json && pnpm build`
Expected: both succeed.

- [ ] **Step 3: Verify by hand**

Run `pnpm dev`, then in the browser:
1. Clear site data, load `/` → lands on `/who-are-you`.
2. Choose a corporation → lands on `/corp`, sidebar shows only Events, header shows the corporation name.
3. Click Switch → returns to `/who-are-you`.
4. Choose the DMU → lands on `/dmu`, sidebar shows five items, header shows the DMU.
5. Reload → stays on `/dmu` without asking again.

Record the outcome of each step in your report.

- [ ] **Step 4: Commit**

```bash
cd apps/frontend
git add src/components/app-sidebar.tsx
git commit -m "frontend: shape navigation to the declared role"
```

---

## Task 6: Cross-role notice

**Files:**
- Create: `apps/frontend/src/components/identity/role-mismatch-notice.tsx`
- Modify: `apps/frontend/src/routes/corp/index.tsx`, `apps/frontend/src/routes/dmu/index.tsx`

**Interfaces:**
- Consumes: `useIdentity` (Task 2), `identityLabel` (Task 1).
- Produces: `<RoleMismatchNotice expected="corp" | "dmu" />`

- [ ] **Step 1: Write the notice**

Create `apps/frontend/src/components/identity/role-mismatch-notice.tsx`:

```tsx
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
```

- [ ] **Step 2: Place it on both landing pages**

In `src/routes/corp/index.tsx`, add `<RoleMismatchNotice expected="corp" />` directly below `<PageHeader ... />`. In `src/routes/dmu/index.tsx`, add `<RoleMismatchNotice expected="dmu" />` in the same position. Import it from `@/components/identity/role-mismatch-notice` in both.

- [ ] **Step 3: Typecheck and build**

Run: `cd apps/frontend && pnpm exec tsc --noEmit -p tsconfig.json && pnpm build`
Expected: both succeed.

- [ ] **Step 4: Verify by hand**

Run `pnpm dev`. As the DMU, navigate directly to `/corp`: the page still renders, with the notice above it offering a switch. Confirm no 403, no redirect, and no blocked content. Then switch to a corporation and confirm the notice disappears. Record both in your report.

- [ ] **Step 5: Run the full suite**

Run: `cd apps/frontend && pnpm test`
Expected: PASS (19 tests).

- [ ] **Step 6: Commit**

```bash
cd apps/frontend
git add src/components/identity/role-mismatch-notice.tsx src/routes/corp/index.tsx src/routes/dmu/index.tsx
git commit -m "frontend: offer a role switch instead of blocking cross-role pages"
```

---

## Done when

- Loading `/` with no stored identity lands on the who-are-you screen; with one, it lands on `/corp` or `/dmu`.
- The chosen identity shows in the header, survives a reload, and is changeable in one click.
- A corrupt or unknown stored value degrades to the who-are-you screen rather than crashing, and storage that throws does not take the app down.
- Navigation shows only what belongs to the declared role.
- Templates and Modules live under `/dmu/admin` and are reachable.
- Visiting a cross-role page renders it with an offer to switch — never a block.
- `pnpm test`, `pnpm exec tsc --noEmit` and `pnpm build` all pass.
