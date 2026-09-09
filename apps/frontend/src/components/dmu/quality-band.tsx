import { formatConstant } from '@/lib/format-constant'
import { cn } from '@/lib/utils'
import type { QualitySummary, ThresholdStatus } from '@/types/dmcu'

function formatRate(value: number | null): string {
  if (value === null) return '—'
  return `${Math.round(value * 100)}%`
}

function ThresholdRow({ item }: { item: ThresholdStatus }) {
  const missed = item.met === false
  return (
    <li
      data-threshold={item.name}
      data-met={item.met === null ? 'unknown' : item.met ? 'true' : 'false'}
      className={cn(
        'flex items-baseline justify-between gap-3 rounded-md px-3 py-1.5 text-sm',
        missed ? 'bg-alert-red-surface text-alert-red' : 'text-foreground',
      )}
    >
      <span className="font-medium">{formatConstant(item.name)}</span>
      <span className="tabular-nums text-muted-foreground">
        {formatRate(item.actual)}
        <span className="ml-2 text-xs">
          {item.met === true ? 'Met' : item.met === false ? 'Below' : 'Waiting'}
        </span>
      </span>
    </li>
  )
}

type QualityBandProps = {
  summary: QualitySummary
  className?: string
}

export function QualityBand({ summary, className }: QualityBandProps) {
  if (summary.scored_count === 0) {
    return (
      <p className={cn('text-sm text-muted-foreground', className)}>
        No scored reports yet.
      </p>
    )
  }

  const missed = summary.thresholds.some((item) => item.met === false)

  return (
    <section
      className={cn(
        'rounded-md border px-3 py-3',
        missed ? 'border-alert-red/30' : 'border-border',
        className,
      )}
      aria-label="Quality thresholds"
    >
      <p className="mb-2 text-xs font-medium text-muted-foreground">
        Quality against PM thresholds
        <span className="ml-2 tabular-nums">
          {summary.scored_count} scored
        </span>
      </p>
      <ul className="grid gap-1 sm:grid-cols-2 xl:grid-cols-3">
        {summary.thresholds.map((item) => (
          <ThresholdRow key={item.name} item={item} />
        ))}
      </ul>
    </section>
  )
}
