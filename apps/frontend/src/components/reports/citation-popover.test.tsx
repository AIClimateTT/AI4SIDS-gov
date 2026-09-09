// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CitationPopover } from '@/components/reports/citation-popover'
import type { Fact } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

function sampleFact(overrides: Partial<Fact> = {}): Fact {
  return {
    metric: 'incidents_by_corporation',
    value: 42,
    unit: 'incidents',
    scope: { corporation: 'arima_borough_corporation' },
    breakdown: null,
    verification: 'validated',
    citation: {
      cid: 'C001',
      module: 'survey123',
      description: 'Arima incident count',
      query_ref:
        'incidents_by_corporation(corporation=arima_borough_corporation)',
      record_ids: ['GUID-1'],
      as_of: '2025-05-18T16:42:00Z',
    },
    ...overrides,
  }
}

function renderPopover(fact: Fact = sampleFact()) {
  return render(
    <CitationPopover fact={fact}>
      <span>C001</span>
    </CitationPopover>,
  )
}

describe('CitationPopover', () => {
  it('shows the figure, description, and source when opened', () => {
    renderPopover()
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))

    expect(screen.getByText('42 incidents')).toBeTruthy()
    expect(screen.getByText('Arima incident count')).toBeTruthy()
    expect(screen.getByText('Field')).toBeTruthy()
  })

  it('keeps the source query out of the primary view', () => {
    renderPopover()
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))

    expect(
      screen.queryByText(
        'incidents_by_corporation(corporation=arima_borough_corporation)',
      ),
    ).toBeNull()
    expect(screen.queryByText('query_ref')).toBeNull()
  })

  it('reveals Source query under Technical details, never the field name', () => {
    renderPopover()
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))
    fireEvent.click(screen.getByRole('button', { name: 'Technical details' }))

    expect(screen.getByText('Source query')).toBeTruthy()
    expect(
      screen.getByText(
        'incidents_by_corporation(corporation=arima_borough_corporation)',
      ),
    ).toBeTruthy()
    expect(screen.getByText('Incidents By Corporation')).toBeTruthy()
    expect(screen.getByText('Validated')).toBeTruthy()
    expect(screen.queryByText('query_ref')).toBeNull()
  })

  it('names how many records produced the figure, without dumping their ids', () => {
    renderPopover(
      sampleFact({
        citation: {
          ...sampleFact().citation,
          record_ids: [
            'diego_martin_regional_corporati:1:1',
            'penal_debe_regional_corporation:5:1',
            'sangre_grande_regional_corporat:4:1',
          ],
        },
      }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))
    fireEvent.click(screen.getByRole('button', { name: 'Technical details' }))

    expect(screen.getByText('3 records')).toBeTruthy()
    expect(
      screen.queryByText('diego_martin_regional_corporati:1:1'),
    ).toBeNull()
  })

  it('View in table still targets the citation row', () => {
    const target = document.createElement('div')
    target.id = 'citation-C001'
    target.scrollIntoView = vi.fn()
    document.body.appendChild(target)

    renderPopover()
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))
    fireEvent.click(screen.getByRole('button', { name: 'View in table' }))

    expect(target.scrollIntoView).toHaveBeenCalled()
  })
})
