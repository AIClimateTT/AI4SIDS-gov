// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { UploadFieldDataDialog } from '@/components/dmu/upload-field-data-dialog'
import { uploadFieldData } from '@/lib/api/ingest'

vi.mock('@/lib/api/ingest', () => ({ uploadFieldData: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderDialog(client = new QueryClient()) {
  const onOpenChange = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <UploadFieldDataDialog open onOpenChange={onOpenChange} />
    </QueryClientProvider>,
  )
  return onOpenChange
}

function chooseFileAndUpload() {
  const file = new File(['ObjectID,GlobalID\n'], 'export.csv', { type: 'text/csv' })
  fireEvent.change(screen.getByLabelText(/survey123 csv/i), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: 'Upload' }))
  return file
}

describe('UploadFieldDataDialog', () => {
  it('tells the officer every row must be validated', () => {
    renderDialog()

    expect(screen.getByText(/every row must be marked validated/i)).toBeTruthy()
  })

  it('shows what landed, and refreshes the table', async () => {
    vi.mocked(uploadFieldData).mockResolvedValue({
      rows_read: 21,
      rows_inserted: 20,
      rows_updated: 1,
      duplicates_flagged: 2,
      unmapped_values: {},
      pii_columns_dropped: [],
      warnings: [],
    })
    const client = new QueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    renderDialog(client)

    chooseFileAndUpload()

    expect(await screen.findByText(/20 new/)).toBeTruthy()
    expect(screen.getByText(/1 updated/)).toBeTruthy()
    expect(screen.getByText(/2 duplicates/)).toBeTruthy()
    await waitFor(() => expect(invalidate).toHaveBeenCalled())
  })

  it('stays open with the reason when a file is rejected, and refreshes nothing', async () => {
    vi.mocked(uploadFieldData).mockRejectedValue(
      new Error('834 row(s) are not marked Validated (first: row 12).'),
    )
    const client = new QueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const onOpenChange = renderDialog(client)

    chooseFileAndUpload()

    expect(await screen.findByText(/834 row\(s\) are not marked Validated/)).toBeTruthy()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(invalidate).not.toHaveBeenCalled()
  })
})
