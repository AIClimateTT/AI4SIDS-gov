// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Composer } from '@/components/corp/composer'

afterEach(() => {
  cleanup()
})

const CORP = 'diego_martin_regional_corporati'

describe('Composer', () => {
  it('creates an event-less session and hands off the first message', async () => {
    const create = vi.fn().mockResolvedValue({ id: 12 })
    const onStarted = vi.fn()
    render(<Composer corporation={CORP} createSession={create} onStarted={onStarted} />)

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Flooding on Diego Martin Main Road, five houses' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(create).toHaveBeenCalledWith({ corporation: CORP }))
    await waitFor(() =>
      expect(onStarted).toHaveBeenCalledWith(
        12,
        'Flooding on Diego Martin Main Road, five houses',
      ),
    )
  })

  it('does not start a session on empty input', () => {
    const create = vi.fn()
    render(<Composer corporation={CORP} createSession={create} onStarted={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(create).not.toHaveBeenCalled()
  })
})
