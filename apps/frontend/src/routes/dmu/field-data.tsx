import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { formatConstant } from '@/lib/format-constant'
import { useAppForm } from '@/hooks/form'
import { useIngestModule } from '@/lib/queries/ingest'
import type { IngestResult } from '@/types/dmcu'

export const Route = createFileRoute('/dmu/field-data')({ component: IngestPage })

const uploadSchema = z.object({
  file: z.instanceof(File, { message: 'Choose a CSV file to upload' }),
})

function IngestPage() {
  const ingest = useIngestModule()

  const form = useAppForm({
    defaultValues: {
      file: undefined as File | undefined,
    },
    validators: {
      onSubmit: uploadSchema,
    },
    onSubmit: async ({ value }) => {
      if (!value.file) return
      await ingest.mutateAsync({ moduleName: 'survey123', file: value.file })
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ingest"
        description="Upload Survey123 CSV exports into the incident store. To file a situation report, go to /corp instead."
      />

      <ContentCard
        title="Upload file"
        description="Attach a Survey123 CSV export and review the ingest result."
      >
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void form.handleSubmit()
          }}
        >
          <form.AppForm>
            <form.AppField name="file">
              {(field) => (
                <field.FileField label="Survey123 CSV" accept=".csv" />
              )}
            </form.AppField>
            <div className="flex justify-end">
              <form.SubmitButton label="Upload" />
            </div>
          </form.AppForm>
        </form>

        {ingest.isSuccess ? <IngestResultView result={ingest.data} /> : null}

        {ingest.isError ? (
          <p className="mt-4 text-sm text-destructive">{ingest.error.message}</p>
        ) : null}
      </ContentCard>
    </div>
  )
}

/** What landed from a Survey123 upload. */
function IngestResultView({ result }: { result: IngestResult }) {
  const unmappedEntries = Object.entries(result.unmapped_values)

  return (
    <div className="mt-4 space-y-3 border-t pt-4">
      <p className="text-sm font-medium">
        {result.rows_read} rows read · {result.rows_inserted} inserted ·{' '}
        {result.rows_updated} updated · {result.duplicates_flagged} duplicates flagged
      </p>

      {unmappedEntries.length > 0 ? (
        <div className="rounded-md border border-dashed p-3 text-sm">
          <p className="font-medium">Unrecognised values</p>
          <p className="text-muted-foreground">
            These rows were still accepted, but a value the system doesn't
            recognise affects which metrics count them.
          </p>
          <ul className="mt-2 space-y-1">
            {unmappedEntries.map(([column, values]) => (
              <li key={column}>
                <span className="font-medium">{formatConstant(column)}:</span>{' '}
                {values.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.pii_columns_dropped.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          {result.pii_columns_dropped.join(', ')}{' '}
          {result.pii_columns_dropped.length === 1
            ? 'was present in the upload and was not stored.'
            : 'were present in the upload and were not stored.'}
        </p>
      ) : null}
    </div>
  )
}
