import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { DownloadIcon } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'
import { z } from 'zod'

import { DataTable } from '@/components/data-table'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
  SourceBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import { PiiDroppedNotice } from '@/components/submissions/pii-dropped-notice'
import { UnmappedValuesNotice } from '@/components/submissions/unmapped-values-notice'
import { useAppForm } from '@/hooks/form'
import { CORPORATION_LABELS, isCanonicalCorporation } from '@/lib/corporations'
import {
  SURVEY123_CSV_HEADERS,
  downloadCsvTemplate,
} from '@/lib/csv-templates'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { incidentQueries } from '@/lib/queries/incidents'
import { useIngestModule } from '@/lib/queries/ingest'
import type {
  IncidentListItem,
  IncidentListSource,
  IngestResult,
} from '@/types/dmcu'

type FieldDataSearch = { source?: IncidentListSource }

const SOURCE_OPTIONS = [
  { value: 'all' as const, label: 'All' },
  { value: 'survey123' as const, label: 'Field' },
  { value: 'sitreps' as const, label: 'SITREP' },
]

function toSource(value: unknown): IncidentListSource {
  return typeof value === 'string' &&
    SOURCE_OPTIONS.some((option) => option.value === value)
    ? (value as IncidentListSource)
    : 'all'
}

export const Route = createFileRoute('/dmu/field-data')({
  component: IngestPage,
  validateSearch: (search: Record<string, unknown>): FieldDataSearch => ({
    source: toSource(search.source),
  }),
})

const uploadSchema = z.object({
  file: z.instanceof(File, { message: 'Choose a CSV file to upload' }),
})

const columns: ColumnDef<IncidentListItem>[] = [
  {
    accessorKey: 'source',
    header: 'Source',
    cell: ({ row }) => <SourceBadge module={row.original.source} />,
  },
  {
    accessorKey: 'corporation',
    header: 'Corporation',
    cell: ({ row }) => corporationLabel(row.original.corporation),
  },
  {
    accessorKey: 'community',
    header: 'Community',
    cell: ({ row }) => row.original.community || '—',
  },
  {
    accessorKey: 'incident_type',
    header: 'Type',
    cell: ({ row }) =>
      row.original.incident_type
        ? formatConstant(row.original.incident_type)
        : '—',
  },
  {
    accessorKey: 'event_date',
    header: 'Date',
    cell: ({ row }) => formatDay(row.original.event_date),
  },
  {
    accessorKey: 'incident_summary',
    header: 'Summary',
    cell: ({ row }) => (
      <span className="block max-w-xs truncate">
        {row.original.incident_summary || '—'}
      </span>
    ),
  },
  {
    id: 'injuries',
    header: 'Injuries',
    cell: ({ row }) =>
      countLabel(row.original.injuries_occurred, row.original.injuries_count),
  },
  {
    id: 'deaths',
    header: 'Deaths',
    cell: ({ row }) =>
      countLabel(row.original.deaths_occurred, row.original.deaths_count),
  },
  {
    id: 'status',
    header: 'Status',
    cell: ({ row }) => fieldStatus(row.original),
  },
  {
    accessorKey: 'ingested_at',
    header: 'Ingested',
    cell: ({ row }) => formatWhen(row.original.ingested_at),
  },
]

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
        contentClassName="space-y-4"
        action={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              downloadCsvTemplate('survey123.csv', SURVEY123_CSV_HEADERS)
            }
          >
            <DownloadIcon />
            Survey123 template
          </Button>
        }
      >
        <p className="text-sm text-muted-foreground">
          This file must be a Survey123 export. ObjectID and GlobalID are
          required. Dates must be ISO-8601, for example 2024-06-01T09:00:00.
        </p>
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

      <StoredIncidents />
    </div>
  )
}

function StoredIncidents() {
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  })
  const [q, setQ] = useState<string | undefined>()
  const search = Route.useSearch()
  const source = search.source ?? 'all'
  const navigate = Route.useNavigate()

  const listParams = {
    page: pagination.pageIndex + 1,
    pageSize: pagination.pageSize,
    q,
    source,
  }

  const { data, isPending, isError, error, isFetching } = useQuery(
    incidentQueries.list(listParams),
  )

  return (
    <ContentCard
      title="Stored incidents"
      description="Survey123 field observations and corporation situation-report incidents."
      contentClassName="space-y-4"
    >
      {isPending && !data ? <LoadingBlock rows={5} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load incidents"
          description={error.message}
        />
      ) : null}

      {data ? (
        <DataTable
          columns={columns}
          data={data.items}
          total={data.total}
          pagination={pagination}
          isLoading={isFetching}
          onStateChange={(updates) => {
            if (typeof updates.page === 'number') {
              setPagination((prev) => ({
                ...prev,
                pageIndex: Math.max(updates.page - 1, 0),
              }))
            }
            const nextPageSize = updates.pageSize ?? updates.page_size
            if (typeof nextPageSize === 'number') {
              setPagination({
                pageIndex: 0,
                pageSize: nextPageSize,
              })
            }
            if ('q' in updates) {
              setQ(
                typeof updates.q === 'string' && updates.q.length > 0
                  ? updates.q
                  : undefined,
              )
              setPagination((prev) => ({ ...prev, pageIndex: 0 }))
            }
            if ('source' in updates) {
              void navigate({
                search: { source: toSource(updates.source) },
                replace: true,
              })
              setPagination((prev) => ({ ...prev, pageIndex: 0 }))
            }
          }}
          toolbar={{
            search: {
              key: 'q',
              placeholder: 'Search incidents…',
            },
          }}
          filters={[
            {
              type: 'toggle',
              key: 'source',
              label: 'Source',
              options: SOURCE_OPTIONS,
            },
          ]}
          filterValues={{ q, source }}
          features={{
            enablePageSizeSelector: true,
            enableColumnVisibility: true,
          }}
        />
      ) : null}
    </ContentCard>
  )
}

/** What landed from a Survey123 upload. */
function IngestResultView({ result }: { result: IngestResult }) {
  return (
    <div className="mt-4 space-y-3 border-t pt-4">
      <p className="text-sm font-medium">
        {result.rows_read} rows read · {result.rows_inserted} inserted ·{' '}
        {result.rows_updated} updated · {result.duplicates_flagged} duplicates flagged
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

function corporationLabel(value: string | null): string {
  if (!value) return '—'
  if (isCanonicalCorporation(value)) return CORPORATION_LABELS[value]
  return formatConstant(value)
}

function countLabel(occurred: boolean, count: number | null): string {
  if (count != null) return String(count)
  return occurred ? 'Yes' : '—'
}

function fieldStatus(row: IncidentListItem): string {
  if (row.source !== 'survey123') return '—'
  const parts: string[] = []
  if (row.validation_status) parts.push(formatConstant(row.validation_status))
  if (row.is_duplicate) parts.push('Duplicate')
  return parts.join(' · ') || '—'
}
