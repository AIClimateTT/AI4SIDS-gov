// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LogCard } from '@/components/capture/log-card'
import type { CaptureLog } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const log = {
  row_id: '1',
  category: 'resource',
  statement: 'Water tankers deployed to Petit Valley',
  item: null,
  quantity: null,
  unit: null,
  status: null,
} satisfies CaptureLog

describe('LogCard', () => {
  it('reads as prose until it is opened', () => {
    render(<LogCard log={log} missing={[]} onEdit={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByText('Water tankers deployed to Petit Valley')).not.toBeNull()
    expect(screen.queryByLabelText('Statement')).toBeNull()
  })

  it('reports only the changed field as a manual path', async () => {
    const onEdit = vi.fn()
    render(<LogCard log={log} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(onEdit).toHaveBeenCalledWith(
        expect.objectContaining({ quantity: 3 }),
        ['log:1.quantity'],
      ),
    )
    const [, paths] = onEdit.mock.calls[0] as [CaptureLog, string[]]
    expect(paths.length).toBe(1)
  })

  it('does not call onEdit when the officer opens and saves with no changes', async () => {
    const onEdit = vi.fn()
    render(<LogCard log={log} missing={[]} onEdit={onEdit} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull())
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('accepts and renders missing chips, opening the card on click', () => {
    render(
      <LogCard
        log={log}
        missing={[{ path: 'logs[0].quantity', message: 'Quantity of relief item' }]}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Quantity of relief item' }))
    expect(screen.getByLabelText('Quantity')).not.toBeNull()
  })

  it('calls onRemove when Remove is clicked', () => {
    const onRemove = vi.fn()
    render(<LogCard log={log} missing={[]} onEdit={vi.fn()} onRemove={onRemove} />)
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(onRemove).toHaveBeenCalled()
  })
})
