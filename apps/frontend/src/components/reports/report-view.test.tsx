// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ReportView } from '@/components/reports/report-view'
import { violationMessage } from '@/components/reports/violation-message'
import type { ReportDetail } from '@/types/dmcu'

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  Link: ({ children }: { children: React.ReactNode }) => <a href="/x">{children}</a>,
  createLink:
    () =>
    ({ children }: { children: React.ReactNode }) => <a href="/x">{children}</a>,
}))

afterEach(cleanup)

const UUID = '042600c0-f118-452c-ad14-2e91d92fb221'

function report(overrides: Partial<ReportDetail> = {}): ReportDetail {
  return {
    id: UUID,
    template: 'survey123_summary',
    template_version: 100,
    params: { date_from: '2026-01-01', date_to: '2026-11-02' },
    data_requirements: [],
    fact_table: {
      request_id: 'r',
      template: 'survey123_summary',
      params: {},
      generated_at: '2026-11-02T10:00:00',
      facts: [],
      gaps: [],
    } as unknown as ReportDetail['fact_table'],
    narrative: '',
    markdown: 'There were 719 incidents [C001].',
    final_markdown: 'There were 719 incidents.',
    status: 'ok',
    violations: [],
    created_at: '2026-11-02T14:36:00',
    kind: 'survey123',
    title: 'Survey123 summary',
    period: '1 Jan – 2 Nov 2026',
    verified: true,
    older_format: false,
    ...overrides,
  }
}

function renderView(data: ReportDetail) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReportView report={data} />
    </QueryClientProvider>,
  )
}

const NEEDS_REVIEW = {
  status: 'needs_review' as const,
  violations: [
    {
      kind: 'invented_number',
      detail: "Number '99' does not match",
      sentence: 'There were 99 incidents.',
      token: '99',
    },
  ],
}

describe('ReportView', () => {
  it('leads with the title and the clean document', () => {
    renderView(report())

    expect(screen.getByRole('heading', { level: 1, name: 'Survey123 summary' })).toBeTruthy()
    expect(screen.getByText('There were 719 incidents.')).toBeTruthy()
    expect(screen.getByText('Survey123 · Verified')).toBeTruthy()
    expect(screen.getByText('1 Jan – 2 Nov 2026')).toBeTruthy()
  })

  it('keeps internal detail off the page', () => {
    renderView(report())

    const text = document.body.textContent ?? ''
    expect(text).not.toContain(UUID)
    expect(text).not.toMatch(/Parameters|Metrics used|Fact table|C001/)
  })

  it('offers Print and Sources, and no Review when there is nothing to review', () => {
    renderView(report())

    expect(screen.getByRole('button', { name: 'Sources' })).toBeTruthy()
    expect(screen.getByText('Print')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Review' })).toBeNull()
  })

  it('puts the report ID and template version in the Sources panel', () => {
    renderView(report())

    fireEvent.click(screen.getByRole('button', { name: 'Sources' }))

    expect(document.body.textContent).toContain(UUID)
    expect(document.body.textContent).toContain('survey123_summary')
  })

  it('says when a report needs review, in plain words', () => {
    renderView(report(NEEDS_REVIEW))

    expect(screen.getByText(/1 problem needs checking/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Review' })).toBeTruthy()
    expect(document.body.textContent).not.toContain('invented_number')
  })

  it('shows problems and citation markers once Review is open', () => {
    renderView(report(NEEDS_REVIEW))

    fireEvent.click(screen.getByRole('button', { name: 'Review' }))

    expect(screen.getByText("The figure 99 doesn't match any source.")).toBeTruthy()
    expect(screen.getByText(/There were 99 incidents\./)).toBeTruthy()
    expect(document.body.textContent).toContain('C001')
  })

  it('keeps the report on the page beside an open panel', () => {
    renderView(report({ ...NEEDS_REVIEW, markdown: 'There were 99 incidents.' }))

    fireEvent.click(screen.getByRole('button', { name: 'Review' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('complementary', { name: 'Review' })).toBeTruthy()
    expect(document.querySelector('article mark')).toBeTruthy()
  })

  it('closes a panel from its button and from its close control', () => {
    renderView(report(NEEDS_REVIEW))
    const review = screen.getByRole('button', { name: 'Review' })

    fireEvent.click(review)
    expect(review.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(review)
    expect(screen.queryByRole('complementary')).toBeNull()
    expect(screen.getByText('There were 719 incidents.')).toBeTruthy()

    fireEvent.click(review)
    fireEvent.click(screen.getByRole('button', { name: 'Close Review' }))
    expect(screen.queryByRole('complementary')).toBeNull()
  })

  it('shows one panel at a time', () => {
    renderView(report(NEEDS_REVIEW))

    fireEvent.click(screen.getByRole('button', { name: 'Review' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sources' }))

    expect(screen.getByRole('complementary', { name: 'Sources' })).toBeTruthy()
    expect(screen.queryByRole('complementary', { name: 'Review' })).toBeNull()
  })

  it('shows citation markers beside Sources, without highlighting problems', () => {
    renderView(report({ ...NEEDS_REVIEW, markdown: 'There were 99 incidents [C001].' }))

    fireEvent.click(screen.getByRole('button', { name: 'Sources' }))

    expect(document.querySelector('article')?.textContent).toContain('C001')
    expect(document.querySelector('article mark')).toBeNull()
  })

  it('returns to the clean report when the last claim has its verdict', () => {
    const pending = {
      quality_eval: {
        claims: {
          claims: [
            {
              claim_id: 'c1',
              sentence: 'A team is on standby [C001].',
              cited_cids: ['C001'],
              number_tokens: [],
              critical: false,
              auto_verdict: 'pending_semantic',
              human_verdict: null,
            },
          ],
        },
      } as unknown as ReportDetail['quality_eval'],
    }
    const client = new QueryClient()
    const { rerender } = render(
      <QueryClientProvider client={client}>
        <ReportView report={report(pending)} />
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Review' }))

    rerender(
      <QueryClientProvider client={client}>
        <ReportView report={report()} />
      </QueryClientProvider>,
    )

    expect(screen.queryByRole('complementary')).toBeNull()
    expect(document.querySelector('article')?.textContent).not.toContain('C001')
  })

  it('offers Review for claims waiting on a verdict', () => {
    renderView(
      report({
        quality_eval: {
          claims: {
            claims: [
              {
                claim_id: 'c1',
                sentence: 'A team is on standby [C001].',
                cited_cids: ['C001'],
                number_tokens: [],
                critical: false,
                auto_verdict: 'pending_semantic',
                human_verdict: null,
              },
            ],
          },
        } as unknown as ReportDetail['quality_eval'],
      }),
    )

    expect(screen.getByRole('button', { name: 'Review' })).toBeTruthy()
  })

  it.each(['queued', 'running', 'failed'] as const)(
    'shows only the state of a %s report',
    (status) => {
      renderView(report({ status, final_markdown: '', markdown: '', error: 'It broke' }))

      expect(screen.queryByRole('button', { name: 'Sources' })).toBeNull()
      expect(screen.queryByRole('button', { name: 'Review' })).toBeNull()
      expect(screen.queryByText('Print')).toBeNull()
    },
  )

  it('marks an older report', () => {
    renderView(report({ older_format: true }))

    expect(screen.getByText('Older format')).toBeTruthy()
  })
})

describe('violationMessage', () => {
  it.each([
    ['invented_number', '99', "The figure 99 doesn't match any source."],
    ['missing_citation', null, 'This sentence has a figure with no source.'],
    ['misattributed_number', '7', 'The figure 7 belongs to a different source.'],
    ['empty_narrative', null, 'The report cites no sources.'],
    ['something_new', null, 'This sentence needs checking.'],
  ])('%s reads plainly', (kind, token, expected) => {
    expect(violationMessage(kind, token)).toBe(expected)
  })
})
