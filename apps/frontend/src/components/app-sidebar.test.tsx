// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { IdentityProvider } from '@/hooks/use-identity'
import { SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { Identity } from '@/lib/identity'

import { AppSidebar, isNavItemActive } from './app-sidebar'

afterEach(() => {
  document.body.innerHTML = ''
})

/** Every path the sidebar links to, plus a nested page under one of them. */
const DMU_PATHS = [
  '/dmu',
  '/dmu/reports',
  '/dmu/reports/new',
  '/dmu/field-data',
  '/dmu/whatsapp',
  '/dmu/admin/templates',
  '/dmu/admin/modules',
  '/dmu/admin/quality',
  '/dmu/admin/users',
]

async function renderSidebar(
  initialPath: string,
  identity: Identity | null = { role: 'dmu' },
) {
  const rootRoute = createRootRoute({
    component: () => (
      <IdentityProvider identity={identity}>
        <TooltipProvider>
          <SidebarProvider>
            <AppSidebar />
          </SidebarProvider>
        </TooltipProvider>
      </IdentityProvider>
    ),
  })
  const routes = DMU_PATHS.map((path) =>
    createRoute({
      getParentRoute: () => rootRoute,
      path,
      component: () => null,
    }),
  )
  const router = createRouter({
    routeTree: rootRoute.addChildren(routes),
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  })

  render(<RouterProvider router={router as never} />)
  await screen.findByText('DMCU Reports')
}

/** Group label → link texts, in DOM order. */
function navGroups(): Array<{ label: string; links: string[] }> {
  return Array.from(
    document.querySelectorAll<HTMLElement>('[data-slot="sidebar-group"]'),
  ).map((group) => ({
    label:
      group.querySelector('[data-slot="sidebar-group-label"]')?.textContent ??
      '',
    links: Array.from(group.querySelectorAll('a')).map((a) => a.textContent),
  }))
}

function linkNamed(name: string): HTMLElement {
  return screen.getByRole('link', { name })
}

/**
 * `SidebarMenuButton` surfaces `isActive` as a bare `data-active` attribute
 * (present when active, absent otherwise) — that is what the sidebar's
 * `data-[active]:` styles key on, so it is what we assert.
 */
function isHighlighted(name: string): boolean {
  return linkNamed(name).hasAttribute('data-active')
}

describe('AppSidebar', () => {
  it('shows only Operations to a DMU officer', async () => {
    await renderSidebar('/dmu')

    expect(navGroups()).toEqual([
      {
        label: 'Operations',
        links: ['Dashboard', 'Reports', 'Field data', 'WhatsApp'],
      },
    ])
  })

  it('adds Administration for an admin identity', async () => {
    await renderSidebar('/dmu', { role: 'admin' })

    expect(navGroups()).toEqual([
      {
        label: 'Operations',
        links: ['Dashboard', 'Reports', 'Field data', 'WhatsApp'],
      },
      {
        label: 'Administration',
        links: ['Templates', 'Modules', 'Quality', 'Users'],
      },
    ])
  })

  it('calls the quality page "Quality" without moving it', async () => {
    await renderSidebar('/dmu', { role: 'admin' })

    expect(linkNamed('Quality').getAttribute('href')).toBe('/dmu/admin/quality')
  })

  it('highlights the current section, and only that section', async () => {
    await renderSidebar('/dmu/admin/modules', { role: 'admin' })

    expect(isHighlighted('Modules')).toBe(true)
    // The dashboard is a prefix of every DMU path; it must not light up here.
    expect(isHighlighted('Dashboard')).toBe(false)
    expect(isHighlighted('Templates')).toBe(false)
  })

  it('treats nested pages as part of their section', async () => {
    await renderSidebar('/dmu/reports/new')

    expect(isHighlighted('Reports')).toBe(true)
    expect(isHighlighted('Dashboard')).toBe(false)
  })

  it('highlights the dashboard only on the dashboard', async () => {
    await renderSidebar('/dmu')

    expect(isHighlighted('Dashboard')).toBe(true)
    expect(isHighlighted('Reports')).toBe(false)
  })

  it('shows no navigation groups to a corp identity', async () => {
    await renderSidebar('/dmu', {
      role: 'corp',
      corporation: 'san_juan_laventille_regional_co',
    })

    expect(navGroups()).toEqual([])
  })
})

describe('isNavItemActive', () => {
  it('matches the exact path and ignores trailing slashes', () => {
    expect(isNavItemActive('/dmu', '/dmu', true)).toBe(true)
    expect(isNavItemActive('/dmu/', '/dmu', true)).toBe(true)
  })

  it('does not treat an exact item as a prefix', () => {
    expect(isNavItemActive('/dmu/reports', '/dmu', true)).toBe(false)
  })

  it('matches children of a section but not lookalike siblings', () => {
    expect(isNavItemActive('/dmu/reports/42', '/dmu/reports')).toBe(true)
    expect(isNavItemActive('/dmu/reportsx', '/dmu/reports')).toBe(false)
  })
})
