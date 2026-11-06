import { useMemo, useState } from 'react'

import { factsByCid } from '@/components/reports/citation-display'
import { CitationMarkdown } from '@/components/reports/citation-markdown'
import { pendingClaims, ReportReviewSheet } from '@/components/reports/report-review-sheet'
import { ReportSourcesSheet } from '@/components/reports/report-sources-sheet'
import { ReportTypeBadge } from '@/components/reports/report-type-badge'
import { ButtonLink, PageHeader, StatusBadge } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import { formatWhen } from '@/lib/format-when'
import type { ReportDetail } from '@/types/dmcu'

function problemsLine(count: number): string {
  return count === 1
    ? '1 problem needs checking. Review before issuing.'
    : `${count} problems need checking. Review before issuing.`
}

export function ReportView({ report }: { report: ReportDetail }) {
  const [panel, setPanel] = useState<'sources' | 'review' | null>(null)

  const sourceByCid = useMemo(() => {
    const map: Record<string, string> = {}
    for (const fact of report.fact_table.facts ?? []) {
      map[fact.citation.cid] = fact.citation.module
    }
    return map
  }, [report])
  const citedFacts = useMemo(() => factsByCid(report.fact_table.facts), [report])

  const finished = report.status === 'ok' || report.status === 'needs_review'
  const problemCount = report.violations.length
  const hasReview = finished && (problemCount > 0 || pendingClaims(report).length > 0)
  const reviewing = panel === 'review'

  return (
    <div className="space-y-6">
      <PageHeader
        title={report.title}
        description={report.period ?? undefined}
        actions={
          finished ? (
            <>
              {hasReview ? (
                <Button type="button" variant="outline" onClick={() => setPanel('review')}>
                  Review
                </Button>
              ) : null}
              <Button type="button" variant="outline" onClick={() => setPanel('sources')}>
                Sources
              </Button>
              <ButtonLink
                to="/dmu/print/$reportId"
                params={{ reportId: report.id }}
                search={{ auto: true }}
                target="_blank"
              >
                Print
              </ButtonLink>
            </>
          ) : null
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <ReportTypeBadge
          kind={report.kind}
          verified={report.verified}
          olderFormat={report.older_format}
        />
        <StatusBadge status={report.status} />
        <span className="text-sm text-muted-foreground">{formatWhen(report.created_at)}</span>
      </div>

      {report.status === 'queued' || report.status === 'running' ? (
        <ContentCard title="Generating">
          <p className="text-sm text-muted-foreground">
            This report is still generating. This page refreshes until it finishes.
          </p>
        </ContentCard>
      ) : null}

      {report.status === 'failed' ? (
        <ContentCard title="Generation failed">
          <p className="text-sm text-destructive">
            {report.error ?? 'Report generation failed.'}
          </p>
        </ContentCard>
      ) : null}

      {finished ? (
        <>
          {problemCount > 0 ? (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
              {problemsLine(problemCount)}
            </p>
          ) : null}
          <ContentCard>
            <article className="mx-auto max-w-[46rem]">
              {reviewing ? (
                <CitationMarkdown
                  markdown={report.markdown}
                  violations={report.violations}
                  sourceByCid={sourceByCid}
                  factsByCid={citedFacts}
                />
              ) : (
                <CitationMarkdown markdown={report.final_markdown} />
              )}
            </article>
          </ContentCard>
          <ReportSourcesSheet
            report={report}
            open={panel === 'sources'}
            onOpenChange={(open) => setPanel(open ? 'sources' : null)}
          />
          {hasReview ? (
            <ReportReviewSheet
              report={report}
              open={reviewing}
              onOpenChange={(open) => setPanel(open ? 'review' : null)}
            />
          ) : null}
        </>
      ) : null}
    </div>
  )
}
