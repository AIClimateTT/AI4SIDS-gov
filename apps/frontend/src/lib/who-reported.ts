import { alertSeverity } from '@/components/shared/alert-level-badge'
import { CANONICAL_CORPORATIONS, CORPORATION_LABELS } from '@/lib/corporations'
import type { CanonicalCorporation } from '@/lib/corporations'
import type { SubmissionSummary } from '@/types/dmcu'

export type ReportingWindowHours = 24 | 168 | 720

export type CorporationReportStatus = {
  corporation: CanonicalCorporation
  label: string
  /** The corporation's most recent filing, however old, or null if it never filed. */
  latest: SubmissionSummary | null
  inWindow: boolean
}

/**
 * One row per corporation, so one that filed nothing cannot silently vanish.
 *
 * Corporations to chase come first, in corporation order: during an event that
 * is what an officer opens this to find. Then those who reported, most severe
 * alert first, so the worst place is at the top of that group.
 */
export function deriveWhoReported(
  submissions: SubmissionSummary[],
  now: Date,
  windowHours: ReportingWindowHours,
): { reportedCount: number; rows: CorporationReportStatus[] } {
  const latestByCorporation = new Map<string, SubmissionSummary>()
  for (const submission of submissions) {
    const current = latestByCorporation.get(submission.corporation)
    if (!current || new Date(submission.as_at) > new Date(current.as_at)) {
      latestByCorporation.set(submission.corporation, submission)
    }
  }

  const cutoff = now.getTime() - windowHours * 3_600_000
  const rows = CANONICAL_CORPORATIONS.map((corporation) => {
    const latest = latestByCorporation.get(corporation) ?? null
    return {
      corporation,
      label: CORPORATION_LABELS[corporation],
      latest,
      inWindow: latest !== null && new Date(latest.as_at).getTime() >= cutoff,
    }
  })

  // Array.prototype.sort is stable, so equal rows keep corporation order and
  // don't reshuffle on every refetch.
  rows.sort((a, b) => {
    const reported = Number(a.inWindow) - Number(b.inWindow)
    if (reported !== 0 || !a.inWindow) return reported
    return (
      alertSeverity(b.latest?.alert_level ?? 'none') -
      alertSeverity(a.latest?.alert_level ?? 'none')
    )
  })

  return { reportedCount: rows.filter((row) => row.inWindow).length, rows }
}

export function highestAlert(rows: CorporationReportStatus[]): CorporationReportStatus | null {
  return (
    rows
      .filter((row) => row.inWindow)
      .reduce<CorporationReportStatus | null>(
        (worst, row) =>
          !worst ||
          alertSeverity(row.latest?.alert_level ?? 'none') >
            alertSeverity(worst.latest?.alert_level ?? 'none')
            ? row
            : worst,
        null,
      ) ?? null
  )
}

export function lastFiledLabel(asAt: string | null, now: Date): string {
  if (!asAt) return 'Never filed'
  const hours = Math.floor((now.getTime() - new Date(asAt).getTime()) / 3_600_000)
  if (hours < 1) return 'Just now'
  if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? '1 day ago' : `${days} days ago`
}
