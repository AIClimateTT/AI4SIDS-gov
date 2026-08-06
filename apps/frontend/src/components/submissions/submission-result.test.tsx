// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SubmissionResult } from '@/components/submissions/submission-result'
import type { SubmissionIngestResult } from '@/types/dmcu'

const baseResult: SubmissionIngestResult = {
  submission_id: 1,
  sequence_no: 3,
  incidents_read: 10,
  incidents_inserted: 6,
  incidents_updated: 2,
  logs_read: 0,
  logs_inserted: 0,
  row_errors: [],
  unmapped_values: {},
  pii_columns_dropped: [],
}

describe('SubmissionResult', () => {
  it('sums inserted and updated for the accepted-count headline', () => {
    render(<SubmissionResult result={baseResult} />)

    expect(screen.getByText('8 of 10 incident rows accepted')).not.toBeNull()
  })

  it('omits the log headline when no log rows were read', () => {
    render(<SubmissionResult result={baseResult} />)

    expect(screen.queryByText(/log rows accepted/)).toBeNull()
  })

  it('shows the log headline when logs were read', () => {
    render(
      <SubmissionResult
        result={{ ...baseResult, logs_read: 4, logs_inserted: 3 }}
      />,
    )

    expect(
      screen.getByText('3 of 4 situation log rows accepted'),
    ).not.toBeNull()
  })

  it('renders row_number verbatim without adding a header offset', () => {
    // The backend already enumerates from 2 because the header is row 1. If
    // this test starts failing because the row shows 3 instead of 2, someone
    // added a second offset — that is the regression this guards.
    render(
      <SubmissionResult
        result={{
          ...baseResult,
          row_errors: [{ file: 'incidents', row_number: 2, reason: 'missing community' }],
        }}
      />,
    )

    expect(screen.getByRole('cell', { name: '2' })).not.toBeNull()
  })

  it('lists unmapped values and the pii reassurance line', () => {
    render(
      <SubmissionResult
        result={{
          ...baseResult,
          unmapped_values: { incident_type: ['sinkhole'] },
          pii_columns_dropped: ['Name of Person'],
        }}
      />,
    )

    expect(screen.getByText(/sinkhole/)).not.toBeNull()
    expect(
      screen.getByText(/Name of Person.*was present in the upload and was not stored\./),
    ).not.toBeNull()
  })
})
