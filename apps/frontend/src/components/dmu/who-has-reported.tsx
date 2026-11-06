import { Link } from '@tanstack/react-router'

import { AlertLevelBadge } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import { lastFiledLabel } from '@/lib/who-reported'
import type {
  CorporationReportStatus,
  ReportingWindowHours,
} from '@/lib/who-reported'

const WINDOWS: { hours: ReportingWindowHours; label: string; phrase: string }[] = [
  { hours: 24, label: '24 hours', phrase: 'the last 24 hours' },
  { hours: 168, label: '7 days', phrase: 'the last 7 days' },
  { hours: 720, label: '30 days', phrase: 'the last 30 days' },
]

export function windowPhrase(windowHours: ReportingWindowHours): string {
  return WINDOWS.find((option) => option.hours === windowHours)?.phrase ?? ''
}

export function reportingHeadline(
  reportedCount: number,
  total: number,
  windowHours: ReportingWindowHours,
): string {
  return `${reportedCount} of ${total} in ${windowPhrase(windowHours)}`
}

export function WhoHasReported({
  rows,
  reportedCount,
  windowHours,
  onWindowChange,
  now,
}: {
  rows: CorporationReportStatus[]
  reportedCount: number
  windowHours: ReportingWindowHours
  onWindowChange: (hours: ReportingWindowHours) => void
  now: Date
}) {
  return (
    <ContentCard
      title="Who has reported"
      description={reportingHeadline(reportedCount, rows.length, windowHours)}
      contentClassName="space-y-3"
    >
      <div className="flex gap-1">
        {WINDOWS.map((option) => (
          <Button
            key={option.hours}
            type="button"
            size="sm"
            variant={windowHours === option.hours ? 'default' : 'outline'}
            onClick={() => onWindowChange(option.hours)}
          >
            {option.label}
          </Button>
        ))}
      </div>
      <ul className="divide-y">
        {rows.map((row) => (
          <li
            key={row.corporation}
            className="flex items-center justify-between gap-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <Link
                to="/dmu/corporations/$corporation"
                params={{ corporation: row.corporation }}
                className="font-medium underline-offset-4 hover:underline"
              >
                {row.label}
              </Link>
              <p className="text-xs text-muted-foreground">
                {row.latest && !row.inWindow ? 'Last filed ' : ''}
                {row.latest
                  ? lastFiledLabel(row.latest.as_at, now).toLowerCase()
                  : 'Never filed'}
              </p>
            </div>
            {row.inWindow && row.latest ? (
              <AlertLevelBadge level={row.latest.alert_level} />
            ) : null}
          </li>
        ))}
      </ul>
    </ContentCard>
  )
}
