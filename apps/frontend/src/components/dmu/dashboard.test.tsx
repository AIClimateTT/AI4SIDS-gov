// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRouter,
} from '@tanstack/react-router'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useQualitySummary } from '@/lib/queries/quality'
import { Route } from '@/routes/dmu/index'

vi.mock('@/components/identity/role-mismatch-notice', () => ({
  RoleMismatchNotice: () => null,
}))
vi.mock('@/lib/queries/quality', async (original) => ({
  ...(await original<typeof import('@/lib/queries/quality')>()),
  useQualitySummary: vi.fn(() => ({ data: undefined, isPending: true, isError: false })),
}))
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn((url: string) =>
      Promise.resolve({
        data:
          url === '/overview'
            ? { incident_count_survey123: 0, incident_count_sitreps: 0, report_count: 0, needs_review_count: 0, recent_reports: [] }
            : [],
      }),
    ),
  },
}))

afterEach(cleanup)

describe('DMU dashboard', () => {
  it('does not load or show the quality band', async () => {
    const Dashboard = Route.options.component as React.ComponentType
    const router = createRouter({
      routeTree: createRootRoute({ component: Dashboard }),
      history: createMemoryHistory({ initialEntries: ['/'] }),
    })
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )

    await screen.findByText('Survey123 incidents')

    expect(useQualitySummary).not.toHaveBeenCalled()
  })
})
