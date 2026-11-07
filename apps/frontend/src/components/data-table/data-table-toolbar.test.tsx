// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { afterEach, describe, expect, it } from 'vitest'

import { DataTableToolbar } from './data-table-toolbar'
import type { FilterConfig, SelectFilterConfig, ToggleFilterConfig } from './types'

const STATUS_FILTER: ToggleFilterConfig = {
  type: 'toggle',
  key: 'status',
  label: 'Status',
  options: [
    { label: 'All', value: 'all' },
    { label: 'Needs review', value: 'needs_review' },
    { label: 'OK', value: 'ok' },
  ],
}

const KIND_FILTER: SelectFilterConfig = {
  type: 'select',
  key: 'kind',
  label: 'Type',
  options: [
    { label: 'All types', value: 'all' },
    { label: 'Minister', value: 'minister' },
  ],
}

function Host({
  status,
  filter = STATUS_FILTER,
}: {
  status?: string
  filter?: FilterConfig
}) {
  const table = useReactTable({
    data: [],
    columns: [{ accessorKey: 'title', header: 'Title' }],
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <DataTableToolbar
      table={table}
      filters={[filter]}
      filterValues={{ [filter.key]: status }}
      onStateChange={() => {}}
    />
  )
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DataTableToolbar toggle filters', () => {
  it('does not offer Reset when the toggle is on all', () => {
    render(<Host status="all" />)

    expect(screen.getByRole('group', { name: 'Status' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Reset' })).toBeNull()
  })

  it('offers Reset when a restricting toggle value is set', () => {
    render(<Host status="needs_review" />)

    expect(screen.getByRole('button', { name: 'Reset' })).toBeTruthy()
  })
})

describe('DataTableToolbar select filters', () => {
  it('shows the label of the chosen option, not its value', () => {
    render(<Host filter={KIND_FILTER} status="minister" />)

    expect(screen.getByRole('combobox').textContent).toContain('Minister')
    expect(screen.getByRole('combobox').textContent).not.toContain('minister')
  })

  it('does not offer Reset when the select is on all', () => {
    render(<Host filter={KIND_FILTER} status="all" />)

    expect(screen.getByRole('combobox').textContent).toContain('All types')
    expect(screen.queryByRole('button', { name: 'Reset' })).toBeNull()
  })

  it('offers Reset when a restricting option is chosen', () => {
    render(<Host filter={KIND_FILTER} status="minister" />)

    expect(screen.getByRole('button', { name: 'Reset' })).toBeTruthy()
  })

  it('shows the filter name when nothing is chosen', () => {
    render(<Host filter={KIND_FILTER} />)

    expect(screen.getByRole('combobox').textContent).toContain('Type')
  })
})
