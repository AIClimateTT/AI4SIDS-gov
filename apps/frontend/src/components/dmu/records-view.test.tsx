// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RecordsView } from '@/components/dmu/records-view'
import { getIncidents } from '@/lib/api/incidents'
import { getSituationLogs } from '@/lib/api/situation-logs'
import { getSubmissions } from '@/lib/api/submissions'

vi.mock('@/lib/api/incidents', () => ({ getIncidents: vi.fn() }))
vi.mock('@/lib/api/situation-logs', () => ({ getSituationLogs: vi.fn() }))
vi.mock('@/lib/api/submissions', async (original) => ({
  ...(await original<typeof import('@/lib/api/submissions')>()),
  getSubmissions: vi.fn(),
}))

const ARIMA = 'arima_borough_corporation'

beforeEach(() => {
  vi.mocked(getIncidents).mockResolvedValue({
    items: [
      {
        id: 'sitreps:1',
        source: 'sitreps',
        corporation: ARIMA,
        community: 'Arima',
        incident_type: 'flooding',
        event_date: '2026-06-01',
        incident_summary: 'Flooded road',
        injuries_occurred: false,
        injuries_count: null,
        deaths_occurred: false,
        deaths_count: null,
        ingested_at: '2026-06-01T10:00:00Z',
        validation_status: null,
        is_duplicate: null,
      },
    ],
    total: 1,
  })
  vi.mocked(getSituationLogs).mockResolvedValue({
    items: [
      {
        id: 1,
        corporation: ARIMA,
        submission_id: 7,
        as_at: '2026-06-01T10:00:00',
        event_title: 'June rains',
        category: 'activity',
        statement: 'CERT on standby',
        item: null,
        quantity: null,
        unit: null,
        status: null,
      },
    ],
    total: 1,
  })
  vi.mocked(getSubmissions).mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderView(search = {}, onSearchChange = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RecordsView search={search} onSearchChange={onSearchChange} />
    </QueryClientProvider>,
  )
  return onSearchChange
}

describe('RecordsView', () => {
  it('lists corporation incidents only, by default', async () => {
    renderView()

    expect(await screen.findByText('Flooded road')).toBeTruthy()
    expect(getIncidents).toHaveBeenCalledWith(
      expect.objectContaining({ source: 'sitreps' }),
    )
  })

  it('opens with the corporation and filing from the URL', async () => {
    renderView({ corporation: ARIMA, submission_id: 7 })

    await waitFor(() =>
      expect(getIncidents).toHaveBeenCalledWith(
        expect.objectContaining({ corporation: ARIMA, submissionId: 7 }),
      ),
    )
    expect(getSubmissions).toHaveBeenCalledWith({ corporation: ARIMA })
  })

  it('shows situation logs on their tab, with the same filters', async () => {
    renderView({ tab: 'logs', corporation: ARIMA, submission_id: 7 })

    expect(await screen.findByText('CERT on standby')).toBeTruthy()
    expect(getSituationLogs).toHaveBeenCalledWith(
      expect.objectContaining({ corporation: ARIMA, submissionId: 7 }),
    )
    expect(getIncidents).not.toHaveBeenCalled()
  })

  it('asks to change tab when one is chosen', async () => {
    const onSearchChange = renderView()

    fireEvent.click(screen.getByRole('button', { name: 'Situation logs' }))

    expect(onSearchChange).toHaveBeenCalledWith(expect.objectContaining({ tab: 'logs' }))
  })

  it('warns that an incident moves to the filing that last updated it', async () => {
    renderView({ corporation: ARIMA })

    expect(await screen.findByText(/filing that last updated them/i)).toBeTruthy()
  })
})
