import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { useState } from 'react'

import { DataTable } from '@/components/data-table'
import { EmptyState, LoadingBlock } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import {
  CORPORATION_LABELS,
  CORPORATION_OPTIONS,
  isCanonicalCorporation,
} from '@/lib/corporations'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { incidentQueries } from '@/lib/queries/incidents'
import { situationLogQueries } from '@/lib/queries/situation-logs'
import { submissionQueries } from '@/lib/queries/submissions'
import type { IncidentListItem, SituationLogItem } from '@/types/dmcu'

export type RecordsSearch = {
  tab?: 'incidents' | 'logs'
  corporation?: string
  submission_id?: number
}

function corporationLabel(value: string | null): string {
  if (!value) return '—'
  return isCanonicalCorporation(value) ? CORPORATION_LABELS[value] : value
}

const INCIDENT_COLUMNS: ColumnDef<IncidentListItem>[] = [
  {
    accessorKey: 'corporation',
    header: 'Corporation',
    cell: ({ row }) => corporationLabel(row.original.corporation),
  },
  {
    accessorKey: 'event_date',
    header: 'Date',
    cell: ({ row }) => formatDay(row.original.event_date),
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
    accessorKey: 'incident_summary',
    header: 'Description',
    cell: ({ row }) => row.original.incident_summary || '—',
  },
  {
    accessorKey: 'injuries_count',
    header: 'Injuries',
    cell: ({ row }) => row.original.injuries_count ?? '—',
  },
  {
    accessorKey: 'deaths_count',
    header: 'Deaths',
    cell: ({ row }) => row.original.deaths_count ?? '—',
  },
]

const LOG_COLUMNS: ColumnDef<SituationLogItem>[] = [
  {
    accessorKey: 'corporation',
    header: 'Corporation',
    cell: ({ row }) => corporationLabel(row.original.corporation),
  },
  {
    accessorKey: 'as_at',
    header: 'As at',
    cell: ({ row }) => formatWhen(row.original.as_at),
  },
  {
    accessorKey: 'event_title',
    header: 'Event',
    cell: ({ row }) => row.original.event_title || '—',
  },
  {
    accessorKey: 'category',
    header: 'Category',
    cell: ({ row }) => formatConstant(row.original.category),
  },
  { accessorKey: 'statement', header: 'Statement' },
  {
    accessorKey: 'quantity',
    header: 'Quantity',
    cell: ({ row }) =>
      row.original.quantity === null
        ? '—'
        : `${row.original.quantity} ${row.original.unit ?? ''}`.trim(),
  },
]

export function RecordsView({
  search,
  onSearchChange,
  lockedCorporation,
}: {
  search: RecordsSearch
  onSearchChange: (next: RecordsSearch) => void
  /** Show only this corporation's records, on its own page. */
  lockedCorporation?: string
}) {
  const tab = search.tab ?? 'incidents'
  const corporation = lockedCorporation ?? search.corporation
  const locked = lockedCorporation !== undefined
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 10 })
  const [q, setQ] = useState<string | undefined>()

  const shared = {
    page: pagination.pageIndex + 1,
    pageSize: pagination.pageSize,
    q,
    corporation,
    submissionId: search.submission_id,
  }
  const incidents = useQuery({
    ...incidentQueries.list({ ...shared, source: 'sitreps' }),
    enabled: tab === 'incidents',
  })
  const logs = useQuery({
    ...situationLogQueries.list(shared),
    enabled: tab === 'logs',
  })
  const filings = useQuery({
    ...submissionQueries.list({ corporation }),
    enabled: !!corporation,
  })

  const active = tab === 'incidents' ? incidents : logs
  const filingOptions = (filings.data ?? []).map((filing) => ({
    value: String(filing.id),
    label: `#${filing.sequence_no} · ${formatWhen(filing.as_at)}`,
  }))

  const tableProps = {
    total: active.data?.total ?? 0,
    pagination,
    isLoading: active.isFetching,
    onStateChange: (updates: Record<string, unknown>) => {
      if (typeof updates.page === 'number') {
        const page = updates.page
        setPagination((prev) => ({ ...prev, pageIndex: Math.max(page - 1, 0) }))
      }
      const nextPageSize = updates.pageSize ?? updates.page_size
      if (typeof nextPageSize === 'number') {
        setPagination({ pageIndex: 0, pageSize: nextPageSize })
      }
      if ('q' in updates) {
        setQ(typeof updates.q === 'string' && updates.q ? updates.q : undefined)
        setPagination((prev) => ({ ...prev, pageIndex: 0 }))
      }
      if ('corporation' in updates) {
        setPagination((prev) => ({ ...prev, pageIndex: 0 }))
        onSearchChange({
          tab,
          corporation:
            typeof updates.corporation === 'string'
              ? updates.corporation
              : undefined,
        })
      }
      if ('submission_id' in updates) {
        setPagination((prev) => ({ ...prev, pageIndex: 0 }))
        onSearchChange({
          ...search,
          submission_id: updates.submission_id
            ? Number(updates.submission_id)
            : undefined,
        })
      }
    },
    toolbar: { search: { key: 'q', placeholder: 'Search…' } },
    filters: [
      ...(locked
        ? []
        : [
            {
              type: 'select' as const,
              key: 'corporation',
              label: 'Corporation',
              options: CORPORATION_OPTIONS,
            },
          ]),
      ...(corporation
        ? [
            {
              type: 'select' as const,
              key: 'submission_id',
              label: 'Filed report',
              options: filingOptions,
            },
          ]
        : []),
    ],
    filterValues: {
      q,
      corporation,
      submission_id: search.submission_id
        ? String(search.submission_id)
        : undefined,
    },
    features: { enablePageSizeSelector: true, enableColumnVisibility: true },
  }

  return (
    <ContentCard
      title={tab === 'incidents' ? 'Incidents' : 'Situation logs'}
      description={
        locked
          ? 'Unverified records filed by this corporation.'
          : 'Unverified records filed by corporations. Survey123 records are on the Field data page.'
      }
      contentClassName="space-y-4"
      action={
        locked ? undefined : (
          <div className="flex gap-2">
            {(['incidents', 'logs'] as const).map((value) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={tab === value ? 'default' : 'outline'}
                onClick={() => {
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                  onSearchChange({ ...search, tab: value })
                }}
              >
                {value === 'incidents' ? 'Incidents' : 'Situation logs'}
              </Button>
            ))}
          </div>
        )
      }
    >
      {corporation ? (
        <p className="text-sm text-muted-foreground">
          Incidents appear under the filing that last updated them.
        </p>
      ) : null}

      {active.isPending && !active.data ? <LoadingBlock rows={5} /> : null}

      {active.isError ? (
        <EmptyState
          title="Could not load records"
          description={active.error.message}
        />
      ) : null}

      {tab === 'incidents' && incidents.data ? (
        <DataTable
          columns={
            locked
              ? INCIDENT_COLUMNS.filter((column) => column.header !== 'Corporation')
              : INCIDENT_COLUMNS
          }
          data={incidents.data.items}
          {...tableProps}
        />
      ) : null}
      {tab === 'logs' && logs.data ? (
        <DataTable
          columns={LOG_COLUMNS}
          data={logs.data.items}
          {...tableProps}
        />
      ) : null}
    </ContentCard>
  )
}
