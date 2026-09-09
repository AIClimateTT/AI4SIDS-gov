import { Button } from '@/components/ui/button'
import { useRateReport } from '@/lib/queries/reports'
import { cn } from '@/lib/utils'

const SCORES = [1, 2, 3, 4, 5] as const

type ReportRatingProps = {
  onRate: (rating: number) => void
  disabled?: boolean
  value?: number
}

export function ReportRating({ onRate, disabled, value }: ReportRatingProps) {
  if (disabled) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Report usefulness">
      {SCORES.map((score) => (
        <Button
          key={score}
          type="button"
          size="sm"
          variant={value === score ? 'default' : 'outline'}
          aria-label={`Rate ${score} out of 5`}
          aria-pressed={value === score}
          onClick={() => onRate(score)}
        >
          {score}
        </Button>
      ))}
    </div>
  )
}

export function ReportRatingField({
  reportId,
  disabled,
  className,
}: {
  reportId: string
  disabled?: boolean
  className?: string
}) {
  const rate = useRateReport(reportId)
  if (disabled) return null

  return (
    <div className={cn('space-y-1.5', className)}>
      <p className="text-xs text-muted-foreground">How useful was this briefing?</p>
      <ReportRating
        value={rate.data?.rating}
        onRate={(rating) => rate.mutate({ reportId, rating })}
      />
    </div>
  )
}
