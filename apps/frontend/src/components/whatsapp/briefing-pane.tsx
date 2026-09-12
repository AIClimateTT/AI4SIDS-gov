import { CitationMarkdown } from '@/components/reports'
import { factsByCid } from '@/components/reports/citation-display'
import { ButtonLink, EmptyState } from '@/components/shared'
import { SubmissionResult } from '@/components/submissions/submission-result'
import { Button } from '@/components/ui/button'
import { FILE_TO_STORE_WARNING } from '@/components/whatsapp/review-briefing-sheet'
import { isReportJobPending } from '@/lib/queries/reports'
import type {
  ReportDetail,
  SubmissionIngestResult,
  WhatsAppDraft,
} from '@/types/dmcu'

export const BRIEFING_EMPTY_TITLE =
  'Generate a provisional briefing from the included rows'

export const BRIEFING_STALE_COPY =
  'Working set changed — regenerate to update the briefing.'

export function WhatsAppBriefingPane({
  draft,
  report,
  includedCount,
  briefingPending,
  promotePending,
  onReview,
  onPromote,
  briefingError,
  promoteError,
  promoteResults,
}: {
  draft: WhatsAppDraft
  report?: ReportDetail
  includedCount: number
  briefingPending: boolean
  promotePending: boolean
  onReview: () => void
  onPromote: () => void
  briefingError?: string
  promoteError?: string
  promoteResults?: SubmissionIngestResult[] | null
}) {
  const reportPending = isReportJobPending(report?.status)
  const generating = briefingPending || reportPending
  const markdown = report?.markdown ?? ''
  const failed = report?.status === 'failed'
  const citedFacts = factsByCid(report?.fact_table.facts)
  const sourceByCid: Record<string, string> = {}
  for (const [cid, fact] of Object.entries(citedFacts)) {
    sourceByCid[cid] = fact.citation.module
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {draft.briefing_stale && markdown ? (
          <p className="text-xs text-muted-foreground">{BRIEFING_STALE_COPY}</p>
        ) : null}
        {!draft.briefing_report_id && !generating ? (
          <EmptyState className="w-full" title={BRIEFING_EMPTY_TITLE} />
        ) : generating && !markdown ? (
          <p className="text-sm text-muted-foreground">Generating briefing…</p>
        ) : failed ? (
          <p className="text-sm text-destructive">
            {report?.error ?? 'Briefing generation failed.'}
          </p>
        ) : markdown ? (
          <>
            <CitationMarkdown
              markdown={markdown}
              sourceByCid={sourceByCid}
              factsByCid={citedFacts}
            />
            {draft.briefing_report_id ? (
              <ButtonLink
                variant="outline"
                size="sm"
                to="/dmu/reports/$reportId"
                params={{ reportId: draft.briefing_report_id }}
              >
                Open report
              </ButtonLink>
            ) : null}
          </>
        ) : (
          <EmptyState className="w-full" title={BRIEFING_EMPTY_TITLE} />
        )}
        {promoteResults
          ? promoteResults.map((result) => (
              <SubmissionResult key={result.submission_id} result={result} />
            ))
          : null}
      </div>
      <div className="shrink-0 space-y-2 border-t bg-background px-4 py-3">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={includedCount === 0 || promotePending}
            onClick={onPromote}
          >
            {promotePending ? 'Filing…' : 'File to store'}
          </Button>
          <Button
            type="button"
            disabled={includedCount === 0 || generating}
            onClick={onReview}
          >
            Review & brief
          </Button>
        </div>
        <p className="text-right text-xs text-muted-foreground">
          {FILE_TO_STORE_WARNING}
        </p>
        {briefingError ? (
          <p className="text-sm text-destructive">{briefingError}</p>
        ) : null}
        {promoteError ? (
          <p className="text-sm text-destructive">{promoteError}</p>
        ) : null}
      </div>
    </div>
  )
}
