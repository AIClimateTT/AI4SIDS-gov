// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WhatsAppSourceForm } from '@/components/whatsapp/source-form'

afterEach(() => {
  cleanup()
})

describe('WhatsAppSourceForm', () => {
  it('submits pasted text and not a file', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<WhatsAppSourceForm onSubmit={onSubmit} />)
    fireEvent.change(screen.getByRole('textbox', { name: /paste the hour/i }), {
      target: { value: 'Diego Martin: 5 houses flooded' },
    })
    fireEvent.click(screen.getByRole('button', { name: /extract/i }))
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ text: 'Diego Martin: 5 houses flooded' }),
      ),
    )
    expect(onSubmit.mock.calls[0][0].file).toBeUndefined()
  })

  it('submits a txt file and not text', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<WhatsAppSourceForm onSubmit={onSubmit} />)
    fireEvent.click(screen.getByRole('tab', { name: /upload/i }))
    const file = new File(['[15/08/2026, 14:32:10] Jane: hello'], 'hour.txt', {
      type: 'text/plain',
    })
    fireEvent.change(screen.getByLabelText(/whatsapp export/i), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: /extract/i }))
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ file })),
    )
    expect(onSubmit.mock.calls[0][0].text).toBeUndefined()
  })

  it('does not submit when paste is empty', () => {
    const onSubmit = vi.fn()
    render(<WhatsAppSourceForm onSubmit={onSubmit} />)
    fireEvent.click(screen.getByRole('button', { name: /extract/i }))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
