import type { CitationViolation } from '@/types/dmcu'
import { violationMessage } from '@/components/reports/violation-message'
import { ContentCard } from '@/components/shared/content-card'

type ViolationsPanelProps = {
  violations: CitationViolation[]
}

export function ViolationsPanel({ violations }: ViolationsPanelProps) {
  if (violations.length === 0) return null

  return (
    <ContentCard
      title="Problems found"
      description="Check these before relying on this report. Flagged sentences are highlighted in the text."
    >
      <ul className="list-disc space-y-2 pl-5 text-sm">
        {violations.map((violation, index) => (
          <li key={`${violation.kind}-${index}`}>
            {violationMessage(violation.kind, violation.token)}
            {violation.sentence ? (
              <p className="mt-1 text-muted-foreground italic">
                “{violation.sentence}”
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </ContentCard>
  )
}
