import type { CitationViolation } from '@/types/dmcu'
import { ContentCard } from '@/components/shared/content-card'

type ViolationsPanelProps = {
  violations: CitationViolation[]
}

export function ViolationsPanel({ violations }: ViolationsPanelProps) {
  if (violations.length === 0) return null

  return (
    <ContentCard
      title="Citation violations"
      description="This report needs review before it can be trusted. Flagged sentences are highlighted in the narrative when matched."
    >
      <ul className="list-disc space-y-2 pl-5 text-sm">
        {violations.map((violation, index) => (
          <li key={`${violation.kind}-${index}`}>
            <span className="font-medium">{violation.kind}</span>
            {': '}
            {violation.detail}
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
