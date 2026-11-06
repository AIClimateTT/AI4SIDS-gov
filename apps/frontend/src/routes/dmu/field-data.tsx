import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { FileTextIcon, UploadIcon } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

import { DataTable } from '@/components/data-table'
import { UploadFieldDataDialog } from '@/components/dmu/upload-field-data-dialog'
import { NewReportDialog } from '@/components/reports/new-report-dialog'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import {
  CORPORATION_OPTIONS,
  corporationShortLabel,
  isCanonicalCorporation,
} from '@/lib/corporations'
import { formatConstant } from '@/lib/format-constant'
import { formatDay } from '@/lib/format-when'
import { incidentQueries } from '@/lib/queries/incidents'
import { overviewQueries } from '@/lib/queries/overview'
import type { IncidentListItem } from '@/types/dmcu'

export const Route = createFileRoute('/dmu/field-data')({
  component: FieldDataPage,
})

const columns: ColumnDef<IncidentListItem>[] = [
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
]

function FieldDataPage() {
  const overview = useQuery(overviewQueries.summary())
  const [dialog, setDialog] = useState<'upload' | 'report' | null>(null)
  const uploaded = overview.data?.survey123_last_uploaded_at

  return (
    <div className="space-y-6">
      <PageHeader
        title="Field data"
        description={
          overview.data
            ? `${overview.data.incident_count_survey123.toLocaleString('en-GB')} records verified by field staff${
                uploaded ? ` · last upload ${formatDay(uploaded)}` : ''
              }`
            : 'Survey123 records verified by field staff.'
        }
        actions={
          <>
            <Button type="button" variant="outline" onClick={() => setDialog('upload')}>
              <UploadIcon />
              Upload
            </Button>
            <Button type="button" onClick={() => setDialog('report')}>
              <FileTextIcon />
              Generate report
            </Button>
          </>
        }
      />

      {dialog === 'upload' ? (
        <UploadFieldDataDialog open onOpenChange={(open) => setDialog(open ? 'upload' : null)} />
      ) : null}
      {dialog === 'report' ? (
        <NewReportDialog
          open
          initialKind="survey123"
          onOpenChange={(open) => setDialog(open ? 'report' : null)}
        />
      ) : null}

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
  const [corporation, setCorporation] = useState<string | undefined>()

  const listParams = {
    page: pagination.pageIndex + 1,
    pageSize: pagination.pageSize,
    q,
    source: 'survey123' as const,
    corporation,
  }

  const { data, isPending, isError, error, isFetching } = useQuery(
    incidentQueries.list(listParams),
  )

  return (
    <ContentCard
      title="Records"
      description="Corporation filings are under Incidents & logs."
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
            if ('corporation' in updates) {
              setCorporation(
                typeof updates.corporation === 'string' ? updates.corporation : undefined,
              )
              setPagination((prev) => ({ ...prev, pageIndex: 0 }))
            }
          }}
          toolbar={{
            search: {
              key: 'q',
              placeholder: 'Search records…',
            },
          }}
          filters={[
            {
              type: 'select',
              key: 'corporation',
              label: 'Corporation',
              options: CORPORATION_OPTIONS,
            },
          ]}
          filterValues={{ q, corporation }}
          features={{
            enablePageSizeSelector: true,
            enableColumnVisibility: true,
          }}
        />
      ) : null}
    </ContentCard>
  )
}

function corporationLabel(value: string | null): string {
  if (!value) return '—'
  if (isCanonicalCorporation(value)) return corporationShortLabel(value)
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
