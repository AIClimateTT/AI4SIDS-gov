// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { afterEach, describe, expect, it } from 'vitest'

import { DataTableToolbar } from './data-table-toolbar'
import type { ToggleFilterConfig } from './types'

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

function Host({ status }: { status?: string }) {
  const table = useReactTable({
    data: [],
    columns: [{ accessorKey: 'title', header: 'Title' }],
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <DataTableToolbar
      table={table}
      filters={[STATUS_FILTER]}
      filterValues={{ status }}
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
