import { Link } from '@tanstack/react-router'
import { AlertTriangleIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type NeedsReviewBandProps = {
  count: number
  className?: string
}

/**
 * The one number on the overview that asks for action.
 *
 * State that requires work changes *shape*, not just value: above zero this is
 * a full-width band with its own colour and a route into the filtered queue;
 * at zero it collapses to a quiet line. A count sitting as a sub-label on a
 * stat card reads as telemetry, and telemetry gets skimmed past — which is the
 * failure this component exists to prevent.
 *
 * It is deliberately the only element on the overview allowed to use the alert
 * red outside an alert-level badge, because a report nobody has looked at is
 * the console's own emergency.
 */
export function NeedsReviewBand({ count, className }: NeedsReviewBandProps) {
  if (count <= 0) {
    return (
      <p
        className={cn('text-sm text-muted-foreground', className)}
        data-needs-review="0"
      >
        No reports are waiting for review.
      </p>
    )
  }

  return (
    <Link
      to="/dmu/reports"
      search={{ status: 'needs_review' }}
      data-needs-review={count}
      className={cn(
        'flex items-center gap-3 rounded-md border border-alert-red/30 bg-alert-red-surface px-4 py-3',
        'text-alert-red transition-colors hover:bg-alert-red/15',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-alert-red',
        className,
      )}
    >
      <AlertTriangleIcon className="size-5 shrink-0" aria-hidden="true" />
      <span className="flex-1 text-sm font-medium">
        <span className="tabular-nums">{count}</span>{' '}
        {count === 1 ? 'report needs' : 'reports need'} review
        <span className="ml-2 font-normal opacity-80">
          {count === 1
            ? 'A figure in it could not be traced to the fact it cites.'
            : 'Figures in them could not be traced to the facts they cite.'}
        </span>
      </span>
      <span className="shrink-0 text-sm font-medium underline underline-offset-4">
        Review
      </span>
    </Link>
  )
}
