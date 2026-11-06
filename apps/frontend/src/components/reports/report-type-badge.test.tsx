// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ReportTypeBadge } from '@/components/reports/report-type-badge'
import { reportColumns } from '@/components/reports/report-columns'
import { DataTable } from '@/components/data-table'
import type { ReportListItem } from '@/types/dmcu'

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  Link: ({ children }: { children: React.ReactNode }) => <a href="/r">{children}</a>,
}))

afterEach(cleanup)

const REPORT: ReportListItem = {
  id: '042600c0',
  template: 'minister_situation_report',
  template_version: 101,
  params: { date_from: '2026-01-01', date_to: '2026-11-02' },
  status: 'ok',
  created_at: '2026-11-02T14:36:00',
  kind: 'minister',
  title: 'Minister report',
  period: '1 Jan – 2 Nov 2026',
  verified: false,
  older_format: false,
}

describe('ReportTypeBadge', () => {
  it.each([
    ['minister', false, 'Minister · Unverified'],
    ['corporation', false, 'Corporation · Unverified'],
    ['survey123', true, 'Survey123 · Verified'],
  ] as const)('labels %s reports', (kind, verified, label) => {
    render(<ReportTypeBadge kind={kind} verified={verified} />)
    expect(screen.getByText(label)).toBeTruthy()
  })

  it('gives each kind its own look', () => {
    const classes = (['minister', 'corporation', 'survey123'] as const).map((kind) => {
      const { container } = render(<ReportTypeBadge kind={kind} verified={kind === 'survey123'} />)
      return container.firstElementChild?.className
    })
    expect(new Set(classes).size).toBe(3)
  })

  it('marks an older report', () => {
    render(<ReportTypeBadge kind="other" verified={false} olderFormat />)
    expect(screen.getByText('Older format')).toBeTruthy()
  })
})

describe('reportColumns', () => {
  it('shows the title and period, and no params or version', () => {
    render(
      <DataTable
        columns={reportColumns}
        data={[REPORT]}
        total={1}
        pagination={{ pageIndex: 0, pageSize: 10 }}
        onStateChange={() => {}}
      />,
    )

    expect(screen.getByText('Minister report')).toBeTruthy()
    expect(screen.getByText('1 Jan – 2 Nov 2026')).toBeTruthy()
    expect(screen.getByText('Minister · Unverified')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Date From|v101|042600c0/)
  })
})
