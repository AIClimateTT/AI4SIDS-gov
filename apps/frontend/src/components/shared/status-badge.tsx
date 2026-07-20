import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ReportStatus } from '@/types/dmcu'

const STATUS_LABELS: Record<ReportStatus, string> = {
  ok: 'OK',
  needs_review: 'Needs review',
}

type StatusBadgeProps = {
  status: ReportStatus
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge
      variant={status === 'ok' ? 'secondary' : 'destructive'}
      className={cn(className)}
    >
      {STATUS_LABELS[status]}
    </Badge>
  )
}
