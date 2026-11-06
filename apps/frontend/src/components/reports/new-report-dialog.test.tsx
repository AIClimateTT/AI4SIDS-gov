// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NewReportDialog } from '@/components/reports/new-report-dialog'
import { createReport } from '@/lib/api/reports'

const navigate = vi.fn()

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  useNavigate: () => navigate,
}))
vi.mock('@/lib/api/reports', async (original) => ({
  ...(await original<typeof import('@/lib/api/reports')>()),
  createReport: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(createReport).mockResolvedValue({ id: 'r-1', status: 'queued' } as never)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const TODAY = new Date('2026-11-06T12:00:00')

function renderDialog(initialKind?: 'minister' | 'survey123') {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <NewReportDialog open onOpenChange={() => {}} initialKind={initialKind} today={TODAY} />
    </QueryClientProvider>,
  )
}

function setDate(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

describe('NewReportDialog', () => {
  it('asks a Survey123 summary only for dates and a corporation', () => {
    renderDialog('survey123')

    expect(screen.getByLabelText<HTMLInputElement>(/date from/i).value).toBe('2026-01-01')
    expect(screen.getByLabelText<HTMLInputElement>(/date to/i).value).toBe('2026-11-06')
    expect(screen.queryByLabelText(/ministry response/i)).toBeNull()
    expect(screen.queryByText(/template/i)).toBeNull()
  })

  it('generates a Survey123 summary and opens it', async () => {
    renderDialog('survey123')

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith({
        template: 'survey123_summary',
        params: { date_from: '2026-01-01', date_to: '2026-11-06' },
      }),
    )
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: '/dmu/reports/$reportId',
        params: { reportId: 'r-1' },
      }),
    )
  })

  it('defaults the minister report to the last 7 days', () => {
    renderDialog('minister')

    expect(screen.getByLabelText<HTMLInputElement>(/date from/i).value).toBe('2026-10-30')
  })

  it('changes the default when switching report, unless the date was chosen', () => {
    renderDialog('minister')

    fireEvent.click(screen.getByRole('button', { name: 'Survey123 summary' }))
    expect(screen.getByLabelText<HTMLInputElement>(/date from/i).value).toBe('2026-01-01')

    setDate(/date from/i, '2026-03-01')
    fireEvent.click(screen.getByRole('button', { name: 'Minister report' }))
    expect(screen.getByLabelText<HTMLInputElement>(/date from/i).value).toBe('2026-03-01')
  })

  it('starts on the minister report by default, without the Ministry sections showing yet', () => {
    renderDialog()

    expect(screen.getByLabelText(/date from/i)).toBeTruthy()
    expect(screen.queryByLabelText(/ministry response/i)).toBeNull()
    expect(screen.getByRole('button', { name: 'Next' })).toBeTruthy()
  })

  it('moves the minister report on to the Ministry sections, which can stay blank', async () => {
    renderDialog('minister')
    setDate(/date from/i, '2026-11-01')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByLabelText(/ministry response/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    await waitFor(() => expect(createReport).toHaveBeenCalled())
    const payload = vi.mocked(createReport).mock.calls[0][0]
    expect(payload.template).toBe('minister_situation_report')
    expect(payload.params.date_from).toBe('2026-11-01')
    expect(payload.params.date_to).toBe('2026-11-06')
    expect(payload.params.as_at).toMatch(/^2026-11-06T/)
    expect(payload.params).not.toHaveProperty('ministry_response')
  })

  it('sends what the Ministry wrote', async () => {
    renderDialog('minister')
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.change(await screen.findByLabelText(/ministry response/i), {
      target: { value: 'Coordinators met at 1pm.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    await waitFor(() => expect(createReport).toHaveBeenCalled())
    expect(vi.mocked(createReport).mock.calls[0][0].params.ministry_response).toBe(
      'Coordinators met at 1pm.',
    )
  })

  it('stops a date range that runs backwards', async () => {
    renderDialog('survey123')
    setDate(/date from/i, '2026-12-01')

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    expect(await screen.findByText('The start date is after the end date.')).toBeTruthy()
    expect(createReport).not.toHaveBeenCalled()
  })

  it('stays open and shows the error when generating fails', async () => {
    vi.mocked(createReport).mockRejectedValue(new Error('Server said no'))
    renderDialog('survey123')

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    expect(await screen.findByText('Server said no')).toBeTruthy()
    expect(navigate).not.toHaveBeenCalled()
  })
})
