import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { PlusIcon } from 'lucide-react'

import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { DataTable } from '@/components/data-table'
import { reportColumns } from '@/components/reports/report-columns'
import { NewReportDialog } from '@/components/reports/new-report-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { reportQueries } from '@/lib/queries/reports'
import type { ReportKind, ReportStatus } from '@/types/dmcu'

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
type ReportsSearch = {
  status?: ReportStatus | 'all'
  kind?: ReportKind | 'all'
  older?: boolean
}

const KIND_OPTIONS = [
  { value: 'all' as const, label: 'All types' },
  { value: 'minister' as const, label: 'Minister' },
  { value: 'corporation' as const, label: 'Corporation' },
  { value: 'survey123' as const, label: 'Survey123' },
]

function toKind(value: unknown): ReportKind | 'all' {
  return typeof value === 'string' &&
    KIND_OPTIONS.some((option) => option.value === value)
    ? (value as ReportKind | 'all')
    : 'all'
}

const STATUS_OPTIONS = [
  { value: 'all' as const, label: 'Any status' },
  { value: 'needs_review' as const, label: 'Needs review' },
  { value: 'ok' as const, label: 'Ready' },
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
    kind: toKind(search.kind),
    older: search.older === true ? true : undefined,
  }),
})

function ReportsPage() {
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  })
  const [q, setQ] = useState<string | undefined>()
  const [creating, setCreating] = useState(false)
  const search = Route.useSearch()
  const status = search.status ?? 'all'
  const kind = search.kind ?? 'all'
  const older = search.older === true
  const navigate = Route.useNavigate()

  const listParams = {
    page: pagination.pageIndex + 1,
    pageSize: pagination.pageSize,
    q,
    status,
    kind,
    includeOlder: older,
  }

  const { data, isPending, isError, error, isFetching } = useQuery(
    reportQueries.list(listParams),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Every report, in one place."
        actions={
          <Button type="button" onClick={() => setCreating(true)}>
            <PlusIcon />
            New report
          </Button>
        }
      />

      {creating ? <NewReportDialog open onOpenChange={setCreating} /> : null}

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
            columns={reportColumns}
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
                  search: { ...search, status: toStatus(updates.status) },
                  replace: true,
                })
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }
              if ('kind' in updates) {
                void navigate({
                  search: { ...search, kind: toKind(updates.kind) },
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
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Checkbox
                    checked={older}
                    onCheckedChange={(checked) => {
                      void navigate({
                        search: { ...search, older: checked === true ? true : undefined },
                        replace: true,
                      })
                      setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                    }}
                  />
                  Show older reports
                </label>
              ),
            }}
            filters={[
              {
                type: 'select',
                key: 'kind',
                label: 'Type',
                options: KIND_OPTIONS,
              },
              {
                type: 'select',
                key: 'status',
                label: 'Status',
                options: STATUS_OPTIONS,
              },
            ]}
            filterValues={{ q, status, kind }}
            features={{
              enablePageSizeSelector: true,
              enableColumnVisibility: true,
            }}
          />
        ) : null}
      </ContentCard>
    </div>
  )
}
