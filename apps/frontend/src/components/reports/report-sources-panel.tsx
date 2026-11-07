import { ReportFactTable } from '@/components/reports/fact-table'
import { ReportSidePanel } from '@/components/reports/report-side-panel'
import type { ReportDetail } from '@/types/dmcu'

export function ReportSourcesPanel({
  report,
  onClose,
}: {
  report: ReportDetail
  onClose: () => void
}) {
  return (
    <ReportSidePanel
      title="Sources"
      description="The stored data this report was built from."
      onClose={onClose}
    >
      <ReportFactTable factTable={report.fact_table} compact />
      <p className="text-xs break-all text-muted-foreground">
        {report.template} version {report.template_version} · Report {report.id}
      </p>
    </ReportSidePanel>
  )
}
