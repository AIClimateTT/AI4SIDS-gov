import { ReportRatingField } from '@/components/reports/report-rating'
import { violationMessage } from '@/components/reports/violation-message'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useVerdictClaim } from '@/lib/queries/quality'
import type { ClaimRecord, ReportDetail } from '@/types/dmcu'

export function pendingClaims(report: ReportDetail): ClaimRecord[] {
  return (report.quality_eval?.claims.claims ?? []).filter(
    (claim) => claim.auto_verdict === 'pending_semantic' && claim.human_verdict == null,
  )
}

export function ReportReviewSheet({
  report,
  open,
  onOpenChange,
}: {
  report: ReportDetail
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const verdict = useVerdictClaim(report.id)
  const claims = pendingClaims(report)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Review</SheetTitle>
          <SheetDescription>
            Citation markers are now showing in the report.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-6 px-4 pb-4">
          {report.violations.length > 0 ? (
            <section className="space-y-3">
              <h2 className="text-sm font-medium">Problems found</h2>
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
              <h2 className="text-sm font-medium">Does the source support these?</h2>
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
        </div>
      </SheetContent>
    </Sheet>
  )
}
