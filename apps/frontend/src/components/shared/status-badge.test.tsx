// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { StatusBadge } from '@/components/shared/status-badge'

afterEach(cleanup)

describe('StatusBadge', () => {
  it('calls a finished report ready', () => {
    render(<StatusBadge status="ok" />)
    expect(screen.getByText('Ready')).toBeTruthy()
  })
})
