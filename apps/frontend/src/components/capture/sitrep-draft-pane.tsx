import { useState } from 'react'

import { CitationMarkdown } from '@/components/reports/citation-markdown'
import { ReportFactTable } from '@/components/reports/fact-table'
import { ReportRatingField } from '@/components/reports/report-rating'
import { ViolationsPanel } from '@/components/reports/violations-panel'
import { EmptyState } from '@/components/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  CORPORATION_LABELS,
  type CanonicalCorporation,
} from '@/lib/corporations'
import { cn } from '@/lib/utils'
import type { CaptureSession } from '@/types/dmcu'

/** Draft is the working copy an officer checks figures against; final is the
 * document that gets issued, with every citation marker already stripped by
 * the backend renderer. */
type SitrepView = 'draft' | 'final'

function ViewToggle({
  view,
  onChange,
}: {
  view: SitrepView
  onChange: (next: SitrepView) => void
}) {
  return (
    <div className="ml-auto flex items-center gap-0.5 rounded-lg border bg-muted/50 p-0.5">
      {([
        ['draft', 'Draft'],
        ['final', 'Final'],
      ] as const).map(([value, label]) => (
        <button
          key={value}
          type="button"
          aria-pressed={view === value}
          onClick={() => onChange(value)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            view === value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export function SitrepDraftPane({
  session,
  onPreview,
  onIssue,
  onDownloadPdf,
  previewPending,
  issuePending,
}: {
  session: CaptureSession
  eventTitle?: string | null
  onPreview: () => void
  onIssue: () => void
  onDownloadPdf?: () => void
  previewPending: boolean
  issuePending: boolean
}) {
  const [view, setView] = useState<SitrepView>('draft')
  const sitrep = session.sitrep
  const filed = session.status === 'filed'
  const issueDisabled = filed || previewPending || issuePending

  if (!sitrep) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-4 py-4">
          <EmptyState
            className="w-full"
            title="No sitrep draft yet"
            description="Generate a draft from the facts captured in this conversation."
            action={
              <Button
                type="button"
                disabled={previewPending}
                onClick={onPreview}
              >
                Generate draft
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  const isFinal = view === 'final'
  const corporation =
    CORPORATION_LABELS[session.corporation as CanonicalCorporation] ??
    session.corporation

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          {/* Reads "Not issued" rather than "Draft" so it cannot be mistaken
              for the Draft/Final view toggle sitting beside it. */}
          <Badge variant={filed ? 'secondary' : 'outline'}>
            {filed ? 'Issued' : 'Not issued'}
          </Badge>
          {!filed && sitrep.stale ? (
            <span className="text-xs text-muted-foreground">
              Facts changed — refresh to update the draft.
            </span>
          ) : null}
          <ViewToggle view={view} onChange={setView} />
        </div>

        {isFinal ? (
          <div className="space-y-1 border-b pb-3">
            <p className="text-sm font-medium">{corporation}</p>
            <p className="text-xs text-muted-foreground">
              {session.report_id
                ? `Report ${session.report_id}`
                : 'Not yet issued'}
            </p>
          </div>
        ) : null}

        <CitationMarkdown
          markdown={isFinal ? sitrep.final_markdown : sitrep.markdown}
          violations={isFinal ? [] : sitrep.violations}
        />

        {isFinal ? null : (
          <>
            <ViolationsPanel violations={sitrep.violations} />
            <div>
              <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
                Cited facts
              </h2>
              <ReportFactTable factTable={sitrep.fact_table} />
            </div>
          </>
        )}

        {filed && session.report_id ? (
          <ReportRatingField reportId={session.report_id} />
        ) : null}
      </div>
      <div className="flex shrink-0 items-center justify-end gap-2 border-t bg-background px-4 py-3">
        {filed ? null : (
          <Button
            type="button"
            variant="outline"
            disabled={previewPending}
            onClick={onPreview}
          >
            Refresh
          </Button>
        )}
        {isFinal && onDownloadPdf ? (
          <Button type="button" variant="outline" onClick={onDownloadPdf}>
            Download PDF
          </Button>
        ) : null}
        <Button type="button" disabled={issueDisabled} onClick={onIssue}>
          {filed ? 'Issued' : 'Issue'}
        </Button>
      </div>
    </div>
  )
}
