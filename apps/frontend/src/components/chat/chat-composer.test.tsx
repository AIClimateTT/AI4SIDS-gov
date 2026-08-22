// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ChatComposer } from '@/components/chat/chat-composer'

afterEach(() => {
  cleanup()
})

describe('ChatComposer', () => {
  it('does not submit an empty draft', () => {
    const onSubmit = vi.fn()
    render(
      <ChatComposer
        value=""
        onChange={vi.fn()}
        onSubmit={onSubmit}
        placeholder="Describe what happened…"
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits on Enter and not on Shift+Enter', () => {
    const onSubmit = vi.fn()
    render(
      <ChatComposer
        value="five houses flooded"
        onChange={vi.fn()}
        onSubmit={onSubmit}
        placeholder="Describe what happened…"
      />,
    )

    const composer = screen.getByPlaceholderText('Describe what happened…')
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true })
    expect(onSubmit).not.toHaveBeenCalled()

    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: false })
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('keeps the plus button disabled when no actions are passed', () => {
    render(
      <ChatComposer value="" onChange={vi.fn()} onSubmit={vi.fn()} />,
    )

    expect(
      (screen.getByRole('button', { name: 'Add' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('opens a menu of passed actions from the plus button', () => {
    const onSelect = vi.fn()
    render(
      <ChatComposer
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        actions={[{ label: 'Add an incident', onSelect }]}
      />,
    )

    const add = screen.getByRole('button', { name: 'Add' }) as HTMLButtonElement
    expect(add.disabled).toBe(false)
    fireEvent.click(add)
    fireEvent.click(screen.getByRole('menuitem', { name: 'Add an incident' }))
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('hands a picked file to a file action', () => {
    const onFile = vi.fn()
    render(
      <ChatComposer
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        actions={[{ label: 'Upload incidents CSV', accept: '.csv,text/csv', onFile }]}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Upload incidents CSV' }))
    const picker = screen.getByLabelText('Choose Upload incidents CSV file') as HTMLInputElement
    const file = new File(['Row ID\n1\n'], 'incidents.csv', { type: 'text/csv' })
    fireEvent.change(picker, { target: { files: [file] } })
    expect(onFile).toHaveBeenCalledTimes(1)
    expect(onFile.mock.calls[0][0]).toBe(file)
  })
})
