// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ReportPrintDocument, reportStatusLine } from '@/components/reports/report-print-document'

vi.mock('@tanstack/react-router', async (original) => ({
  ...(await original<typeof import('@tanstack/react-router')>()),
  Link: ({ children }: { children: React.ReactNode }) => <a href="/x">{children}</a>,
}))

afterEach(cleanup)

describe('ReportPrintDocument', () => {
  it('prints the clean text under a small header', () => {
    render(
      <ReportPrintDocument
        title="Minister report"
        statusLine="Unverified"
        markdown="All fourteen corporations."
      />,
    )

    expect(screen.getByText('Minister report')).toBeTruthy()
    expect(screen.getByText('Unverified')).toBeTruthy()
    expect(screen.getByText('All fourteen corporations.')).toBeTruthy()
  })
})

describe('reportStatusLine', () => {
  it('says verified or unverified', () => {
    expect(reportStatusLine({ verified: true, status: 'ok' })).toBe('Verified')
    expect(reportStatusLine({ verified: false, status: 'ok' })).toBe('Unverified')
  })

  it('adds a warning when the report needs review', () => {
    expect(reportStatusLine({ verified: true, status: 'needs_review' })).toBe(
      'Verified · Needs review',
    )
  })
})
