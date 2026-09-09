import { createFileRoute } from '@tanstack/react-router'

import { QualityThresholdChart } from '@/components/dmu/quality-threshold-chart'
import { QualityThresholdTable } from '@/components/dmu/quality-threshold-table'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
  StatCard,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { formatThresholdValue } from '@/lib/quality-display'
import { useQualitySummary } from '@/lib/queries/quality'
import type { QualitySummary } from '@/types/dmcu'

export const Route = createFileRoute('/dmu/admin/quality')({
  component: QualityPage,
})

function QualityPage() {
  const { data, isPending, isError, error } = useQualitySummary()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Quality"
        description="How generated reports and operator ratings sit against the PM thresholds."
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load quality summary"
          description={error.message}
        />
      ) : null}

      {data ? <QualityAnalytics summary={data} /> : null}
    </div>
  )
}

function QualityAnalytics({ summary }: { summary: QualitySummary }) {
  const empty = summary.scored_count === 0 && summary.rating_count === 0
  if (empty) {
    return (
      <p className="text-sm text-muted-foreground">No scored reports yet.</p>
    )
  }

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Scored reports"
          value={`${summary.scored_count} / ${summary.report_count}`}
          hint="Reports with a quality eval"
        />
        <StatCard
          label="Rating mean"
          value={formatThresholdValue('usability_mean', summary.rating_mean)}
          hint={
            summary.rating_count === 1
              ? '1 rating'
              : `${summary.rating_count} ratings`
          }
        />
        <StatCard
          label="Unaided completions"
          value={`${summary.task_succeeded_unaided} / ${summary.task_started}`}
          hint="Named tasks finished without assistance"
        />
      </div>

      <ContentCard
        title="Actual versus threshold"
        description="Each bar is a percent on a shared 0–100 scale. Usability mean is mapped from a 1–5 rating (4.0 is 80%)."
      >
        <QualityThresholdChart thresholds={summary.thresholds} />
      </ContentCard>

      <ContentCard
        title="Thresholds"
        description="Sample is the number of scored reports, ratings, or started tasks behind that rate."
      >
        <QualityThresholdTable thresholds={summary.thresholds} />
      </ContentCard>
    </>
  )
}
