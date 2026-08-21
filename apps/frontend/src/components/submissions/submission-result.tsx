import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { PiiDroppedNotice } from '@/components/submissions/pii-dropped-notice'
import { UnmappedValuesNotice } from '@/components/submissions/unmapped-values-notice'
import type { RowErrorInfo, SubmissionIngestResult } from '@/types/dmcu'

const FILE_LABELS: Record<'incidents' | 'logs', string> = {
  incidents: 'Incidents',
  logs: 'Situation logs',
}

/** Rejected rows for a single filing -- shared between the just-filed
 * result (SubmissionResult) and the read-back page for a filing that was
 * already on file (Task 15's /corp/filings/$submissionId). */
export function RowErrorsTable({ rowErrors }: { rowErrors: RowErrorInfo[] }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-destructive">
        {rowErrors.length} row
        {rowErrors.length === 1 ? '' : 's'} rejected
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Row</TableHead>
            <TableHead>File</TableHead>
            <TableHead>Reason</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rowErrors.map((rowError, index) => (
            <TableRow key={index}>
              <TableCell>
                {/* row_number is already spreadsheet-relative: the backend
                    enumerates rows starting at 2 because the header is row
                    1. Render it as-is — adding another offset here would
                    double-count and send the officer to the wrong line in
                    their own file. */}
                {rowError.row_number}
              </TableCell>
              <TableCell>{FILE_LABELS[rowError.file]}</TableCell>
              <TableCell>{rowError.reason}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/** What landed and what didn't, for a single filing. */
export function SubmissionResult({ result }: { result: SubmissionIngestResult }) {
  const incidentsAccepted = result.incidents_inserted + result.incidents_updated

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm font-medium">
          {incidentsAccepted} of {result.incidents_read} incident rows accepted
        </p>
        {result.logs_read > 0 ? (
          <p className="text-sm font-medium">
            {result.logs_inserted} of {result.logs_read} situation log rows accepted
          </p>
        ) : null}
      </div>

      {result.row_errors.length > 0 ? <RowErrorsTable rowErrors={result.row_errors} /> : null}

      <UnmappedValuesNotice unmappedValues={result.unmapped_values} />

      <PiiDroppedNotice columns={result.pii_columns_dropped} />
    </div>
  )
}
