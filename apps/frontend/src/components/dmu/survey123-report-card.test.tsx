// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Survey123ReportCard } from '@/components/dmu/survey123-report-card'
import { createReport } from '@/lib/api/reports'

const navigate = vi.fn()

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  useNavigate: () => navigate,
}))
vi.mock('@/lib/api/reports', async (original) => ({
  ...(await original<typeof import('@/lib/api/reports')>()),
  createReport: vi.fn().mockResolvedValue({ id: 'r-1', status: 'queued' }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Survey123ReportCard today={new Date('2026-11-05T12:00:00')} />
    </QueryClientProvider>,
  )
}

describe('Survey123ReportCard', () => {
  it('defaults to the start of the year through today', () => {
    renderCard()

    expect(screen.getByLabelText<HTMLInputElement>(/date from/i).value).toBe('2026-01-01')
    expect(screen.getByLabelText<HTMLInputElement>(/date to/i).value).toBe('2026-11-05')
  })

  it('generates the Survey123 summary and opens it', async () => {
    renderCard()

    fireEvent.click(screen.getByRole('button', { name: /generate report/i }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith({
        template: 'survey123_summary',
        params: { date_from: '2026-01-01', date_to: '2026-11-05' },
      }),
    )
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: '/dmu/reports/$reportId',
        params: { reportId: 'r-1' },
      }),
    )
  })
})
