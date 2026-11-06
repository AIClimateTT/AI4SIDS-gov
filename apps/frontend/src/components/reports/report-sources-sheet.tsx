import { ReportFactTable } from '@/components/reports/fact-table'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import type { ReportDetail } from '@/types/dmcu'

export function ReportSourcesSheet({
  report,
  open,
  onOpenChange,
}: {
  report: ReportDetail
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>Sources</SheetTitle>
          <SheetDescription>The stored data this report was built from.</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 pb-4">
          <ReportFactTable factTable={report.fact_table} />
          <p className="text-xs text-muted-foreground">
            {report.template} version {report.template_version} · Report {report.id}
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}
