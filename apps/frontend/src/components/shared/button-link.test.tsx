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

import { ButtonLink } from './button-link'

afterEach(() => {
  document.body.innerHTML = ''
})

async function renderLink() {
  const rootRoute = createRootRoute({
    component: () => (
      <ButtonLink variant="outline" size="sm" to="/dmu/reports">
        Back to reports
      </ButtonLink>
    ),
  })
  const reportsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/dmu/reports',
    component: () => null,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([reportsRoute]),
    history: createMemoryHistory({ initialEntries: ['/dmu/reports'] }),
  })

  render(<RouterProvider router={router as never} />)
  return (await screen.findByRole('link', {
    name: 'Back to reports',
  })) as HTMLAnchorElement
}

describe('ButtonLink', () => {
  it('is a real link, not a button wearing a link costume', async () => {
    const link = await renderLink()

    expect(link.tagName).toBe('A')
    expect(link.getAttribute('href')).toBe('/dmu/reports')
  })

  /**
   * Regression: the previous spelling was `<Button render={<Link />}>`, which
   * routed the anchor through Base UI's button primitive. That warned in the
   * console, and the advertised silencer — `nativeButton={false}` — stamps
   * `role="button"` onto the `<a>`, so assistive tech would announce "button"
   * for a control that still navigates and still opens in a new tab.
   */
  it('keeps its link role and gains no button semantics', async () => {
    const link = await renderLink()

    expect(link.getAttribute('role')).toBeNull()
    expect(link.getAttribute('type')).toBeNull()
  })

  it('still wears the button variant classes', async () => {
    const link = await renderLink()

    // `outline` and `sm` both contribute classes; the element should look
    // exactly like the Button it replaced.
    expect(link.className).toContain('border-border')
    expect(link.className).toContain('h-7')
  })
})
