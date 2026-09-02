import { isAlertLevel } from '@/components/shared/alert-level-badge'
import { formatConstant } from '@/lib/format-constant'
import { formatDay, formatWhen } from '@/lib/format-when'
import { cn } from '@/lib/utils'
import type { SubmissionSummary } from '@/types/dmcu'

/**
 * Background utility per alert level. Separate from AlertLevelBadge's variants
 * because a trajectory block is a solid fill read at a glance, not a bordered
 * pill read as a label.
 */
const BLOCK_CLASS: Record<string, string> = {
  green: 'bg-alert-green',
  yellow: 'bg-alert-yellow',
  orange: 'bg-alert-orange',
  red: 'bg-alert-red',
  discontinued: 'bg-alert-discontinued',
  none: 'bg-alert-none',
}

type AlertTrajectoryProps = {
  /** Oldest first. The caller orders these; this component does not sort. */
  submissions: SubmissionSummary[]
  className?: string
}

/**
 * A corporation's alert level across its filings, in time order.
 *
 * The question this answers is the one a duty officer asks about a region
 * mid-event and cannot currently ask anywhere: *is this getting worse?* A table
 * of timestamps holds the same data and does not answer it — the shape of an
 * escalation is only visible when the levels sit side by side.
 *
 * Each block is a filing, not a unit of time: the corporations file when they
 * file, and stretching blocks to elapsed time would imply a regular cadence the
 * data does not have.
 */
export function AlertTrajectory({
  submissions,
  className,
}: AlertTrajectoryProps) {
  if (submissions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No filings in this window.
      </p>
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      <ol className="flex flex-wrap items-stretch gap-1">
        {submissions.map((submission) => {
          const level = isAlertLevel(submission.alert_level)
            ? submission.alert_level
            : 'none'
          return (
            <li
              key={submission.id}
              className="min-w-[76px] flex-1"
              data-alert-level={submission.alert_level}
            >
              <div
                className={cn('h-2 w-full rounded-sm', BLOCK_CLASS[level])}
                // Colour is never the only encoding: the level is written
                // underneath, and the title carries it for pointer users.
                title={`${formatConstant(submission.alert_level)} as at ${formatWhen(submission.as_at)}`}
              />
              <p className="mt-1.5 text-[0.7rem] font-medium">
                {formatConstant(submission.alert_level)}
              </p>
              <p className="text-[0.65rem] text-muted-foreground tabular-nums">
                {formatDay(submission.as_at)}
              </p>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
