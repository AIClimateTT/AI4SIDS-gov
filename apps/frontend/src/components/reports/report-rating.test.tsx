// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ReportRating } from './report-rating'

describe('ReportRating', () => {
  it('calls onRate with 5 when the last star is clicked', async () => {
    const onRate = vi.fn()
    render(<ReportRating onRate={onRate} />)
    const five = screen.getByRole('button', { name: 'Rate 5 out of 5' })
    five.click()
    expect(onRate).toHaveBeenCalledWith(5)
  })

  it('does not render when the report is still generating', () => {
    const { container } = render(
      <ReportRating onRate={() => undefined} disabled />,
    )
    expect(container.querySelectorAll('button').length).toBe(0)
  })
})
