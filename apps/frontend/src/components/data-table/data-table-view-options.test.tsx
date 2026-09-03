// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import type { ColumnDef } from '@tanstack/react-table'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'

import { DataTableViewOptions } from './data-table-view-options'

type Row = { title: string; status: string }

const columns: ColumnDef<Row>[] = [
  { accessorKey: 'title', header: 'Title' },
  { accessorKey: 'status', header: 'Status' },
  // A display-only column has no accessor and must not be offered for
  // toggling — it is what row actions render into.
  { id: 'actions', header: '', cell: () => null },
]

const rows: Row[] = [{ title: 'Flooding, Sangre Grande', status: 'ok' }]

/** Minimal host: the toggle needs a real table instance to read columns. */
function Host() {
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })
  return <DataTableViewOptions table={table} />
}

beforeAll(() => {
  // Base UI positions the popup with floating-ui, which observes the anchor.
  // jsdom has no ResizeObserver; a no-op is enough for the menu to mount.
  if (typeof window.ResizeObserver === 'undefined') {
    window.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DataTableViewOptions', () => {
  /**
   * Regression: opening the menu threw "Base UI: MenuGroupContext is missing"
   * because the "Toggle columns" label is a Menu.GroupLabel and was rendered
   * without an enclosing Menu.Group. The route error boundary then replaced
   * the whole reports page with "Something went wrong".
   */
  it('opens the column toggle without crashing', async () => {
    render(<Host />)

    fireEvent.click(screen.getByRole('button', { name: 'View' }))

    expect(await screen.findByText('Toggle columns')).toBeTruthy()
  })

  it('lists only the hideable accessor columns as checked items', async () => {
    render(<Host />)

    fireEvent.click(screen.getByRole('button', { name: 'View' }))
    await screen.findByText('Toggle columns')

    const items = screen.getAllByRole('menuitemcheckbox')
    expect(items.map((item) => item.textContent)).toEqual(['Title', 'Status'])
    expect(
      items.every((item) => item.getAttribute('aria-checked') === 'true'),
    ).toBe(true)
  })
})
