// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DataTableFilterToggle } from './data-table-filter-toggle'

const STATUS_FILTER = {
  type: 'toggle' as const,
  key: 'status',
  label: 'Status',
  options: [
    { label: 'All', value: 'all' },
    { label: 'Needs review', value: 'needs_review' },
    { label: 'OK', value: 'ok' },
  ],
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DataTableFilterToggle', () => {
  it('renders each option as a button and marks the current value pressed', () => {
    render(
      <DataTableFilterToggle
        filter={STATUS_FILTER}
        value="needs_review"
        onChange={() => {}}
      />,
    )

    const group = screen.getByRole('group', { name: 'Status' })
    const buttons = screen.getAllByRole('button')

    expect(group).toBeTruthy()
    expect(buttons.map((button) => button.textContent)).toEqual([
      'All',
      'Needs review',
      'OK',
    ])
    expect(
      screen.getByRole('button', { name: 'Needs review' }).getAttribute(
        'aria-pressed',
      ),
    ).toBe('true')
    expect(
      screen.getByRole('button', { name: 'All' }).getAttribute('aria-pressed'),
    ).toBe('false')
  })

  it('treats a missing value as the all option so the queue switcher has a pressed button', () => {
    render(
      <DataTableFilterToggle
        filter={STATUS_FILTER}
        value={undefined}
        onChange={() => {}}
      />,
    )

    expect(
      screen.getByRole('button', { name: 'All' }).getAttribute('aria-pressed'),
    ).toBe('true')
  })

  it('reports the clicked option to onChange', () => {
    const onChange = vi.fn()
    render(
      <DataTableFilterToggle
        filter={STATUS_FILTER}
        value="all"
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'OK' }))

    expect(onChange).toHaveBeenCalledWith('ok')
  })
})
