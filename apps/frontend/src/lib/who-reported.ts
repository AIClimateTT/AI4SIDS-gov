import { CANONICAL_CORPORATIONS, CORPORATION_LABELS } from '@/lib/corporations'
import type { CanonicalCorporation } from '@/lib/corporations'
import { alertSeverity } from '@/components/shared/alert-level-badge'
import type { SubmissionSummary } from '@/types/dmcu'

export type CorporationReportStatus = {
  corporation: CanonicalCorporation
  label: string
  /** Most recent submission in the window, or null if this corporation filed nothing. */
  latest: SubmissionSummary | null
}

/**
 * Derive one row per canonical corporation from a flat list of submissions
 * (already narrowed to a date window server-side). This iterates
 * CANONICAL_CORPORATIONS rather than the submissions, so a corporation that
 * filed nothing in the window still gets a row instead of silently vanishing
 * — that's the whole point of a "who has reported" panel.
 *
 * Reported corporations sort before unreported ones; within each group the most
 * severe alert level comes first, and equal severities keep canonical order.
 */
export function deriveWhoReported(
  submissions: SubmissionSummary[],
): CorporationReportStatus[] {
  const latestByCorporation = new Map<string, SubmissionSummary>()

  for (const submission of submissions) {
    const current = latestByCorporation.get(submission.corporation)
    if (!current || new Date(submission.as_at) > new Date(current.as_at)) {
      latestByCorporation.set(submission.corporation, submission)
    }
  }

  return CANONICAL_CORPORATIONS.map((corporation) => ({
    corporation,
    label: CORPORATION_LABELS[corporation],
    latest: latestByCorporation.get(corporation) ?? null,
  })).sort((a, b) => {
    // Corporations that filed stay above those that did not, as before: a row
    // reading "No reports at this time" is a gap to chase, not a severity.
    const reported = Number(b.latest !== null) - Number(a.latest !== null)
    if (reported !== 0) return reported

    // Then most severe first. An officer opening this during an event is
    // answering "where is it worst", and reading fourteen rows to find the red
    // one is the thing this ordering exists to remove.
    // Equal severity returns 0 rather than falling through to another key.
    // Array.prototype.sort is stable, so ties keep the canonical order this
    // list was built in — which is what keeps the unreported block in
    // CANONICAL_CORPORATIONS order and stops equal-severity rows reshuffling
    // on every refetch.
    return (
      alertSeverity(b.latest?.alert_level ?? 'none') -
      alertSeverity(a.latest?.alert_level ?? 'none')
    )
  })
}
