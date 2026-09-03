// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { AlertTrajectory } from './alert-trajectory'
import type { SubmissionSummary } from '@/types/dmcu'

afterEach(() => {
  document.body.innerHTML = ''
})

function submission(
  id: number,
  alert_level: string,
  as_at = '2023-06-01T00:00:00Z',
): SubmissionSummary {
  return {
    id,
    corporation: 'diego_martin_regional_corporati',
    event_id: 1,
    event_title: 'Adverse Weather June 2023',
    as_at,
    alert_level,
    sequence_no: id,
    incident_count: 0,
    log_count: 0,
  }
}

describe('AlertTrajectory', () => {
  it('renders one block per filing, in the order given', () => {
    render(
      <AlertTrajectory
        submissions={[
          submission(1, 'yellow'),
          submission(2, 'red'),
          submission(3, 'discontinued'),
        ]}
      />,
    )

    const blocks = document.querySelectorAll('li[data-alert-level]')
    expect(blocks).toHaveLength(3)
    expect([...blocks].map((b) => b.getAttribute('data-alert-level'))).toEqual([
      'yellow',
      'red',
      'discontinued',
    ])
  })

  it('writes the level as text under every block', () => {
    // The escalation has to be readable without colour vision, in print, and
    // by a screen reader.
    render(<AlertTrajectory submissions={[submission(1, 'red')]} />)
    expect(screen.getByText('Red')).toBeTruthy()
  })

  it('handles an unrecognised level without breaking the row', () => {
    render(<AlertTrajectory submissions={[submission(1, 'catastrophic')]} />)
    expect(screen.getByText('Catastrophic')).toBeTruthy()
    expect(document.querySelectorAll('li[data-alert-level]')).toHaveLength(1)
  })

  it('says so when there is nothing to plot', () => {
    render(<AlertTrajectory submissions={[]} />)
    expect(screen.getByText('No filings in this window.')).toBeTruthy()
  })
})
