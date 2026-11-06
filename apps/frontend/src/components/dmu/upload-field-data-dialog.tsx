import { useState } from 'react'
import { z } from 'zod'

import { AppDialog } from '@/components/shared'
import { PiiDroppedNotice } from '@/components/submissions/pii-dropped-notice'
import { UnmappedValuesNotice } from '@/components/submissions/unmapped-values-notice'
import { useAppForm } from '@/hooks/form'
import { useUploadFieldData } from '@/lib/queries/ingest'
import type { IngestResult } from '@/types/dmcu'

const uploadSchema = z.object({
  file: z.instanceof(File, { message: 'Choose a CSV file to upload' }),
})

function UploadResult({ result }: { result: IngestResult }) {
  return (
    <div className="space-y-3 border-t pt-4">
      <p className="text-sm font-medium">
        {result.rows_read} rows read · {result.rows_inserted} new · {result.rows_updated}{' '}
        updated · {result.duplicates_flagged} duplicates
      </p>

      <UnmappedValuesNotice unmappedValues={result.unmapped_values} />

      <PiiDroppedNotice columns={result.pii_columns_dropped} />

      {result.warnings?.length ? (
        <div className="rounded-md border border-dashed p-3 text-sm">
          <p className="font-medium">Check before relying on these rows</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export function UploadFieldDataDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const upload = useUploadFieldData()
  const [failure, setFailure] = useState<string | null>(null)

  const form = useAppForm({
    defaultValues: { file: undefined as File | undefined },
    validators: { onSubmit: uploadSchema },
    onSubmit: async ({ value }) => {
      if (!value.file) return
      setFailure(null)
      try {
        await upload.mutateAsync({ file: value.file })
      } catch (error) {
        setFailure(error instanceof Error ? error.message : 'The file could not be uploaded.')
      }
    },
  })

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Upload Survey123 data"
      description="Use the CSV exported from ArcGIS. Every row must be marked Validated, or the whole file is rejected."
      className="sm:max-w-xl"
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
            {(field) => <field.FileField label="Survey123 CSV" accept=".csv" />}
          </form.AppField>
          {failure ? <p className="text-sm text-destructive">{failure}</p> : null}
          {upload.isSuccess ? <UploadResult result={upload.data} /> : null}
          <div className="flex justify-end">
            <form.SubmitButton label="Upload" />
          </div>
        </form.AppForm>
      </form>
    </AppDialog>
  )
}
