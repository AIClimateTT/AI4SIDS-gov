// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { IdentityProvider } from '@/hooks/use-identity'
import { SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { Identity } from '@/lib/identity'

import { AppSidebar, isNavItemActive } from './app-sidebar'

vi.mock('@/lib/api/submissions', async (original) => ({
  ...(await original<typeof import('@/lib/api/submissions')>()),
  getSubmissions: vi.fn().mockResolvedValue([]),
}))

afterEach(() => {
  document.body.innerHTML = ''
})

/** Every path the sidebar links to, plus a nested page under one of them. */
const DMU_PATHS = [
  '/dmu',
  '/dmu/reports',
  '/dmu/records',
  '/dmu/reports/new',
  '/dmu/field-data',
  '/dmu/admin/quality',
  '/dmu/admin/users',
  '/dmu/corporations/$corporation',
]

async function renderSidebar(
  initialPath: string,
  identity: Identity | null = { role: 'dmu' },
) {
  const rootRoute = createRootRoute({
    component: () => (
      <IdentityProvider identity={identity}>
        <QueryClientProvider client={new QueryClient()}>
          <TooltipProvider>
            <SidebarProvider>
              <AppSidebar />
            </SidebarProvider>
          </TooltipProvider>
        </QueryClientProvider>
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

describe('AppSidebar corporations', () => {
  it('lists all fourteen when opened', async () => {
    await renderSidebar('/dmu', { role: 'dmu' })

    fireEvent.click(screen.getByRole('button', { name: /corporations/i }))

    expect(await screen.findByRole('link', { name: /Arima/ })).toBeTruthy()
    const group = Array.from(
      document.querySelectorAll<HTMLElement>('[data-slot="sidebar-group"]'),
    ).find((el) => el.textContent?.includes('Corporations'))
    expect(group?.querySelectorAll('a')).toHaveLength(14)
  })

  it('opens by itself on a corporation page', async () => {
    await renderSidebar('/dmu/corporations/arima_borough_corporation', { role: 'dmu' })

    expect(await screen.findByRole('link', { name: /Arima/ })).toBeTruthy()
  })
})

describe('AppSidebar', () => {
  it('shows only Operations to a DMU officer', async () => {
    await renderSidebar('/dmu')

    expect(navGroups()).toEqual([
      {
        label: 'Operations',
        links: ['Dashboard', 'Reports', 'Incidents & logs', 'Field data'],
      },
      { label: 'Corporations', links: [] },
    ])
  })

  it('adds Administration for an admin identity', async () => {
    await renderSidebar('/dmu', { role: 'admin' })

    expect(navGroups()).toEqual([
      {
        label: 'Operations',
        links: ['Dashboard', 'Reports', 'Incidents & logs', 'Field data'],
      },
      { label: 'Corporations', links: [] },
      {
        label: 'Administration',
        links: ['Quality', 'Users'],
      },
    ])
  })

  it('calls the quality page "Quality" without moving it', async () => {
    await renderSidebar('/dmu', { role: 'admin' })

    expect(linkNamed('Quality').getAttribute('href')).toBe('/dmu/admin/quality')
  })

  it('highlights the current section, and only that section', async () => {
    await renderSidebar('/dmu/admin/users', { role: 'admin' })

    expect(isHighlighted('Users')).toBe(true)
    // The dashboard is a prefix of every DMU path; it must not light up here.
    expect(isHighlighted('Dashboard')).toBe(false)
    expect(isHighlighted('Quality')).toBe(false)
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
