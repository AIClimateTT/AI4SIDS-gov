import { CitationMarkdown } from '@/components/reports/citation-markdown'
import { ReportFactTable } from '@/components/reports/fact-table'
import { ViolationsPanel } from '@/components/reports/violations-panel'
import { EmptyState } from '@/components/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CaptureSession } from '@/types/dmcu'

export function SitrepDraftPane({
  session,
  onPreview,
  onIssue,
  previewPending,
  issuePending,
}: {
  session: CaptureSession
  eventTitle?: string | null
  onPreview: () => void
  onIssue: () => void
  previewPending: boolean
  issuePending: boolean
}) {
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

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={filed ? 'secondary' : 'outline'}>
            {filed ? 'Issued' : 'Draft'}
          </Badge>
          {!filed && sitrep.stale ? (
            <span className="text-xs text-muted-foreground">
              Facts changed — refresh to update the draft.
            </span>
          ) : null}
        </div>
        <CitationMarkdown
          markdown={sitrep.markdown}
          violations={sitrep.violations}
        />
        <ViolationsPanel violations={sitrep.violations} />
        <div>
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
            Cited facts
          </h2>
          <ReportFactTable factTable={sitrep.fact_table} />
        </div>
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
        <Button type="button" disabled={issueDisabled} onClick={onIssue}>
          {filed ? 'Issued' : 'Issue'}
        </Button>
      </div>
    </div>
  )
}
