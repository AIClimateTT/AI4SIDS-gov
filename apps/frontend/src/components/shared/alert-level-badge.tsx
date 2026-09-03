import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'
import { formatConstant } from '@/lib/format-constant'

/**
 * The six values a corporation files against every submission — ALERT_LEVELS in
 * `apps/backend/app/modules/sitreps/models.py`. Kept in the same order as the
 * backend tuple so the two are diffable by eye.
 */
export const ALERT_LEVELS = [
  'green',
  'yellow',
  'orange',
  'red',
  'discontinued',
  'none',
] as const

export type AlertLevel = (typeof ALERT_LEVELS)[number]

/**
 * Severity order for sorting, highest first.
 *
 * `discontinued` outranks `green` deliberately: a corporation that stood down
 * from an alert reported something, and a duty officer scanning the window
 * wants it above a region that was never affected. `none` is last because it
 * means the level was never stated — an unanswered question, and the officer
 * chasing it is doing so after they have handled every stated level.
 */
const SEVERITY: Record<AlertLevel, number> = {
  red: 5,
  orange: 4,
  yellow: 3,
  discontinued: 2,
  green: 1,
  none: 0,
}

export function isAlertLevel(value: string): value is AlertLevel {
  return (ALERT_LEVELS as readonly string[]).includes(value)
}

/**
 * Rank for sorting. An unrecognised value sorts with `none` rather than
 * throwing: the API types `alert_level` as a bare string, so a level added
 * backend-side before the frontend knows about it must not break the table.
 */
export function alertSeverity(value: string): number {
  return isAlertLevel(value) ? SEVERITY[value] : SEVERITY.none
}

const alertLevelBadge = cva(
  // Pill-shaped to stay distinct from buttons, which are structural. The label
  // is always rendered as text — colour is redundant encoding, never the only
  // encoding, and the word is what survives the print stylesheet.
  'inline-flex h-5 w-fit shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      level: {
        green: 'border-alert-green/30 bg-alert-green-surface text-alert-green',
        yellow:
          'border-alert-yellow/30 bg-alert-yellow-surface text-alert-yellow',
        orange:
          'border-alert-orange/30 bg-alert-orange-surface text-alert-orange',
        red: 'border-alert-red/30 bg-alert-red-surface text-alert-red',
        discontinued:
          'border-alert-discontinued/30 bg-alert-discontinued-surface text-alert-discontinued',
        none: 'border-alert-none/30 bg-alert-none-surface text-alert-none',
      },
    },
    defaultVariants: { level: 'none' },
  },
)

type AlertLevelBadgeProps = {
  level: string
  className?: string
} & Omit<VariantProps<typeof alertLevelBadge>, 'level'>

/**
 * An alert level, rendered so severity is visible without reading.
 *
 * Takes a bare `string` because that is what the API returns
 * (`SubmissionSummary.alert_level`). An unrecognised value falls back to the
 * `none` styling and still renders its own label, so a level the backend gains
 * before the frontend does degrades to "unstyled but legible" rather than
 * blank.
 */
export function AlertLevelBadge({ level, className }: AlertLevelBadgeProps) {
  const known = isAlertLevel(level) ? level : 'none'
  return (
    <span
      className={cn(alertLevelBadge({ level: known }), className)}
      data-alert-level={level}
    >
      <span
        aria-hidden="true"
        className="size-1.5 shrink-0 rounded-full bg-current"
      />
      {formatConstant(level)}
    </span>
  )
}
