import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ReportKind } from '@/types/dmcu'

const KIND_LABELS: Record<ReportKind, string> = {
  corporation: 'Corporation',
  minister: 'Minister',
  survey123: 'Survey123',
  other: 'Other',
}

const KIND_CLASSES: Record<ReportKind, string> = {
  corporation: 'border-source-sitrep/30 bg-source-sitrep-surface text-source-sitrep',
  minister: 'border-primary/30 bg-primary/10 text-foreground',
  survey123: 'border-source-field/30 bg-source-field-surface text-source-field',
  other: 'border-border bg-muted text-muted-foreground',
}

/** Which report this is, and whether its figures are verified. Shown wherever a report appears. */
export function ReportTypeBadge({
  kind,
  verified,
  olderFormat = false,
}: {
  kind: ReportKind
  verified: boolean
  olderFormat?: boolean
}) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Badge variant="outline" className={cn(KIND_CLASSES[kind])}>
        {kind === 'other'
          ? KIND_LABELS.other
          : `${KIND_LABELS[kind]} · ${verified ? 'Verified' : 'Unverified'}`}
      </Badge>
      {olderFormat ? <Badge variant="secondary">Older format</Badge> : null}
    </span>
  )
}
