import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { PlusIcon } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

import {
  ButtonLink,
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { DataTable } from '@/components/data-table'
import { reportQueries } from '@/lib/queries/reports'
import type { ReportListItem, ReportStatus } from '@/types/dmcu'
import { formatWhen } from '@/lib/format-when'

/**
 * `status` lives in the URL rather than in component state so the needs-review
 * band on the dashboard can link straight to the filtered queue, and so an
 * officer can bookmark or share it. The backend has always accepted this
 * parameter (`GET /reports?status=`); nothing in the interface sent it.
 */
/**
 * Optional, not required: a bare `/dmu/reports` is still a valid link, and
 * every existing one across the app keeps working. Absent means "all".
 */
type ReportsSearch = { status?: ReportStatus | 'all' }

const STATUS_OPTIONS = [
  { value: 'all' as const, label: 'All' },
  { value: 'needs_review' as const, label: 'Needs review' },
  { value: 'ok' as const, label: 'OK' },
]

function toStatus(value: unknown): ReportStatus | 'all' {
  return typeof value === 'string' &&
    STATUS_OPTIONS.some((option) => option.value === value)
    ? (value as ReportStatus | 'all')
    : 'all'
}

export const Route = createFileRoute('/dmu/reports/')({
  component: ReportsPage,
  validateSearch: (search: Record<string, unknown>): ReportsSearch => ({
    status: toStatus(search.status),
  }),
})

const columns: ColumnDef<ReportListItem>[] = [
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    accessorKey: 'template',
    header: 'Template',
    cell: ({ row }) => (
      <div>
        <p className="font-medium">{row.original.template}</p>
        <p className="text-xs text-muted-foreground">
          v{row.original.template_version}
        </p>
      </div>
    ),
  },
  {
    id: 'params',
    header: 'Params',
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {Object.entries(row.original.params)
          .map(([key, value]) => `${key}=${value}`)
          .join(', ')}
      </span>
    ),
  },
  {
    accessorKey: 'created_at',
    header: 'Created',
    cell: ({ row }) => formatWhen(row.original.created_at),
  },
]

function ReportsPage() {
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  })
  const [q, setQ] = useState<string | undefined>()
  const search = Route.useSearch()
  const status = search.status ?? 'all'
  const navigate = Route.useNavigate()

  const listParams = {
    page: pagination.pageIndex + 1,
    pageSize: pagination.pageSize,
    q,
    status,
  }

  const { data, isPending, isError, error, isFetching } = useQuery(
    reportQueries.list(listParams),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Browse generated briefings and open citation-checked markdown."
        actions={
          <ButtonLink to="/dmu/reports/new">
            <PlusIcon />
            Generate
          </ButtonLink>
        }
      />

      <ContentCard contentClassName="space-y-4">
        {isPending && !data ? <LoadingBlock rows={5} /> : null}

        {isError ? (
          <EmptyState
            title="Could not load reports"
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
              if ('status' in updates) {
                // Filtering changes how many pages exist, so go back to the
                // first one rather than stranding the officer on a page the
                // narrowed list no longer has.
                void navigate({
                  search: { status: toStatus(updates.status) },
                  replace: true,
                })
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }
            }}
            toolbar={{
              search: {
                key: 'q',
                placeholder: 'Search reports…',
              },
              actions: (
                <ButtonLink size="sm" to="/dmu/reports/new">
                  Generate
                </ButtonLink>
              ),
            }}
            filters={[
              {
                type: 'toggle',
                key: 'status',
                label: 'Status',
                options: STATUS_OPTIONS,
              },
            ]}
            filterValues={{ q, status }}
            features={{
              enablePageSizeSelector: true,
              enableColumnVisibility: true,
            }}
            rowActions={(row) => (
              <ButtonLink
                variant="ghost"
                size="sm"
                to="/dmu/reports/$reportId"
                params={{ reportId: row.id }}
              >
                Open
              </ButtonLink>
            )}
          />
        ) : null}
      </ContentCard>
    </div>
  )
}
