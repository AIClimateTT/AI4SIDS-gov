import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ReportStatus } from '@/types/dmcu'

const STATUS_LABELS: Record<ReportStatus, string> = {
  ok: 'OK',
  needs_review: 'Needs review',
  queued: 'Queued',
  running: 'Generating',
  failed: 'Failed',
}

type StatusBadgeProps = {
  status: ReportStatus
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const variant =
    status === 'failed'
      ? 'destructive'
      : status === 'needs_review'
        ? 'destructive'
        : 'secondary'
  return (
    <Badge variant={variant} className={cn(className)}>
      {STATUS_LABELS[status]}
    </Badge>
  )
}
