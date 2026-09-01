import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { PlusIcon } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { DataTable } from '@/components/data-table'
import { reportQueries } from '@/lib/queries/reports'
import type { ReportListItem, ReportStatus } from '@/types/dmcu'

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

const FILTERABLE: ReadonlyArray<ReportStatus | 'all'> = [
  'all',
  'needs_review',
  'ok',
]

function toStatus(value: unknown): ReportStatus | 'all' {
  return typeof value === 'string' &&
    (FILTERABLE as ReadonlyArray<string>).includes(value)
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
    cell: ({ row }) => new Date(row.original.created_at).toLocaleString(),
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
          <Button render={<Link to="/dmu/reports/new" />}>
            <PlusIcon />
            Generate
          </Button>
        }
      />

      <ContentCard contentClassName="space-y-4">
        <div
          role="group"
          aria-label="Filter reports by status"
          className="flex flex-wrap items-center gap-2"
        >
          {FILTERABLE.map((value) => (
            <Button
              key={value}
              size="sm"
              variant={status === value ? 'default' : 'outline'}
              aria-pressed={status === value}
              onClick={() => {
                // Filtering changes how many pages exist, so go back to the
                // first one rather than stranding the officer on a page the
                // narrowed list no longer has.
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                void navigate({ search: { status: value }, replace: true })
              }}
            >
              {value === 'all'
                ? 'All'
                : value === 'needs_review'
                  ? 'Needs review'
                  : 'OK'}
            </Button>
          ))}
        </div>

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
            }}
            toolbar={{
              search: {
                key: 'q',
                placeholder: 'Search reports…',
              },
              actions: (
                <Button size="sm" render={<Link to="/dmu/reports/new" />}>
                  Generate
                </Button>
              ),
            }}
            filterValues={{ q }}
            features={{
              enablePageSizeSelector: true,
              enableColumnVisibility: true,
            }}
            rowActions={(row) => (
              <Button
                variant="ghost"
                size="sm"
                render={
                  <Link
                    to="/dmu/reports/$reportId"
                    params={{ reportId: row.id }}
                  />
                }
              >
                Open
              </Button>
            )}
          />
        ) : null}
      </ContentCard>
    </div>
  )
}
