import { formatConstant } from '@/lib/format-constant'
import {
  formatThresholdValue,
  isLowerBetter,
  thresholdStatusLabel,
} from '@/lib/quality-display'
import { cn } from '@/lib/utils'
import type { ThresholdStatus } from '@/types/dmcu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type QualityThresholdTableProps = {
  thresholds: ThresholdStatus[]
}

export function QualityThresholdTable({
  thresholds,
}: QualityThresholdTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>KPI</TableHead>
          <TableHead>Actual</TableHead>
          <TableHead>Threshold</TableHead>
          <TableHead>Sample</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Note</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {thresholds.map((item) => {
          const missed = item.met === false
          return (
            <TableRow
              key={item.name}
              data-threshold={item.name}
              className={missed ? 'bg-alert-red-surface' : undefined}
            >
              <TableCell className="font-medium">
                {formatConstant(item.name)}
              </TableCell>
              <TableCell className="tabular-nums">
                {formatThresholdValue(item.name, item.actual)}
              </TableCell>
              <TableCell className="tabular-nums">
                {formatThresholdValue(item.name, item.threshold)}
              </TableCell>
              <TableCell className="tabular-nums">{item.sample}</TableCell>
              <TableCell
                className={cn(missed ? 'text-alert-red' : undefined)}
              >
                {thresholdStatusLabel(item.met)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {isLowerBetter(item.name) ? 'Lower is better' : '—'}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
