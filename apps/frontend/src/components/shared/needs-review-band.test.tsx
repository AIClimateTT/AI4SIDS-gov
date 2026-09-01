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

import { NeedsReviewBand } from './needs-review-band'

afterEach(() => {
  document.body.innerHTML = ''
})

/**
 * The band renders a `<Link>`, so it needs a router. A memory router with a
 * stub `/dmu/reports` route is enough to resolve the target and let us assert
 * on the href the officer would actually follow.
 */
async function renderBand(count: number) {
  const rootRoute = createRootRoute()
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <NeedsReviewBand count={count} />,
  })
  const reportsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/dmu/reports',
    validateSearch: (search: Record<string, unknown>) => ({
      status: typeof search.status === 'string' ? search.status : 'all',
    }),
    component: () => null,
  })

  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute, reportsRoute]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })

  render(<RouterProvider router={router as never} />)
  return router
}

describe('NeedsReviewBand', () => {
  it('collapses to a quiet line when nothing needs review', async () => {
    await renderBand(0)
    expect(
      await screen.findByText('No reports are waiting for review.'),
    ).toBeTruthy()
    // No link: there is nothing to go and do.
    expect(document.querySelector('a')).toBeNull()
  })

  it('becomes a link into the filtered queue when work exists', async () => {
    await renderBand(3)
    const link = await screen.findByRole('link')
    // The whole point of the band: it is a route into the work, not a readout.
    expect(link.getAttribute('href')).toContain('/dmu/reports')
    expect(link.getAttribute('href')).toContain('needs_review')
  })

  it('states the count and pluralises it', async () => {
    await renderBand(3)
    expect(await screen.findByText(/reports need/)).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('uses the singular for one report', async () => {
    await renderBand(1)
    expect(await screen.findByText(/report needs/)).toBeTruthy()
  })

  it('explains what a review flag means, not just that one exists', async () => {
    await renderBand(2)
    // A count with no explanation trains officers to dismiss it. The band says
    // what failed: a figure could not be traced to the fact it cites.
    expect(await screen.findByText(/could not be traced/)).toBeTruthy()
  })
})
