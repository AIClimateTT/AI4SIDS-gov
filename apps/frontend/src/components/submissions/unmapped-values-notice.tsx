import { formatConstant } from '@/lib/format-constant'

/**
 * Rows were accepted, but one or more columns held a value the system
 * doesn't recognise, which affects which metrics count them. Shared between
 * the corp situation-report result view and the DMU Survey123 ingest result
 * view — both `SubmissionIngestResult` and `IngestResult` carry
 * `unmapped_values: Record<string, string[]>` with identical semantics.
 */
export function UnmappedValuesNotice({
  unmappedValues,
}: {
  unmappedValues: Record<string, string[]>
}) {
  const entries = Object.entries(unmappedValues)
  if (entries.length === 0) return null

  return (
    <div className="rounded-md border border-dashed p-3 text-sm">
      <p className="font-medium">Unrecognised values</p>
      <p className="text-muted-foreground">
        These rows were still accepted, but a value the system doesn't
        recognise affects which metrics count them.
      </p>
      <ul className="mt-2 space-y-1">
        {entries.map(([column, values]) => (
          <li key={column}>
            <span className="font-medium">{formatConstant(column)}:</span>{' '}
            {values.join(', ')}
          </li>
        ))}
      </ul>
    </div>
  )
}
