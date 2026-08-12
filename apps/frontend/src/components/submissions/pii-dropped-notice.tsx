/**
 * Which columns were present in an upload but stripped before storage.
 * Shared between the corp situation-report result view and the DMU
 * Survey123 ingest result view — both `SubmissionIngestResult` and
 * `IngestResult` carry `pii_columns_dropped: string[]` with identical
 * semantics.
 */
export function PiiDroppedNotice({ columns }: { columns: string[] }) {
  if (columns.length === 0) return null

  return (
    <p className="text-sm text-muted-foreground">
      {columns.join(', ')}{' '}
      {columns.length === 1
        ? 'was present in the upload and was not stored.'
        : 'were present in the upload and were not stored.'}
    </p>
  )
}
