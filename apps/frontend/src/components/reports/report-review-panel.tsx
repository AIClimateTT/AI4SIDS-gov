import { ReportRatingField } from '@/components/reports/report-rating'
import { ReportSidePanel } from '@/components/reports/report-side-panel'
import { violationMessage } from '@/components/reports/violation-message'
import { Button } from '@/components/ui/button'
import { useVerdictClaim } from '@/lib/queries/quality'
import type { ClaimRecord, ReportDetail } from '@/types/dmcu'

export function pendingClaims(report: ReportDetail): ClaimRecord[] {
  return (report.quality_eval?.claims.claims ?? []).filter(
    (claim) => claim.auto_verdict === 'pending_semantic' && claim.human_verdict == null,
  )
}

export function ReportReviewPanel({
  report,
  onClose,
}: {
  report: ReportDetail
  onClose: () => void
}) {
  const verdict = useVerdictClaim(report.id)
  const claims = pendingClaims(report)

  return (
    <ReportSidePanel
      title="Review"
      description={
        report.violations.length > 0
          ? 'Problems are highlighted in the report.'
          : 'Citation markers are showing in the report.'
      }
      onClose={onClose}
    >
      {report.violations.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-sm font-medium">Problems found</h3>
          <ul className="space-y-3 text-sm">
            {report.violations.map((violation, index) => (
              <li key={`${violation.kind}-${index}`}>
                <p>{violationMessage(violation.kind, violation.token)}</p>
                {violation.sentence ? (
                  <p className="mt-1 text-muted-foreground italic">{violation.sentence}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {claims.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-sm font-medium">Does the source support these?</h3>
          <ul className="space-y-3">
            {claims.map((claim) => (
              <li key={claim.claim_id} className="space-y-2">
                <p className="text-sm">{claim.sentence}</p>
                <div className="flex gap-2">
                  {(['supported', 'unsupported'] as const).map((choice) => (
                    <Button
                      key={choice}
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={verdict.isPending}
                      onClick={() =>
                        verdict.mutate({
                          reportId: report.id,
                          claimId: claim.claim_id,
                          verdict: choice,
                        })
                      }
                    >
                      {choice === 'supported' ? 'Supported' : 'Not supported'}
                    </Button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ReportRatingField reportId={report.id} />
    </ReportSidePanel>
  )
}
