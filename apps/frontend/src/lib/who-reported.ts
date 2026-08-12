import { CANONICAL_CORPORATIONS, CORPORATION_LABELS } from '@/lib/corporations'
import type { CanonicalCorporation } from '@/lib/corporations'
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
 * Reported corporations sort before unreported ones; within each group the
 * canonical order is preserved.
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
  })).sort((a, b) => Number(b.latest !== null) - Number(a.latest !== null))
}
