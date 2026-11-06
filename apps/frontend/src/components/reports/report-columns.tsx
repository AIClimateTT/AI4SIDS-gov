import { Link } from '@tanstack/react-router'
import type { ColumnDef } from '@tanstack/react-table'

import { ReportTypeBadge } from '@/components/reports/report-type-badge'
import { StatusBadge } from '@/components/shared'
import { formatWhen } from '@/lib/format-when'
import type { ReportListItem } from '@/types/dmcu'

export const reportColumns: ColumnDef<ReportListItem>[] = [
  {
    accessorKey: 'title',
    header: 'Report',
    cell: ({ row }) => (
      <div>
        <Link
          to="/dmu/reports/$reportId"
          params={{ reportId: row.original.id }}
          className="font-medium underline-offset-4 hover:underline"
        >
          {row.original.title}
        </Link>
        {row.original.period ? (
          <p className="text-xs text-muted-foreground">{row.original.period}</p>
        ) : null}
      </div>
    ),
  },
  {
    accessorKey: 'kind',
    header: 'Type',
    cell: ({ row }) => (
      <ReportTypeBadge
        kind={row.original.kind}
        verified={row.original.verified}
        olderFormat={row.original.older_format}
      />
    ),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    accessorKey: 'created_at',
    header: 'Created',
    cell: ({ row }) => formatWhen(row.original.created_at),
  },
]
