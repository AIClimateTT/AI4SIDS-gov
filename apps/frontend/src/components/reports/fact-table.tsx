import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { citationAnchorId } from '@/components/reports/citation-utils'
import {
  SourceBadge,
  sourceEdgeClass,
  sourceOf,
} from '@/components/shared/source-badge'
import { cn } from '@/lib/utils'
import type { Fact, FactTable } from '@/types/dmcu'

type ReportFactTableProps = {
  factTable: FactTable
  className?: string
}

function formatValue(fact: Fact): string {
  const unit = fact.unit ? ` ${fact.unit}` : ''
  return `${fact.value}${unit}`
}

export function ReportFactTable({
  factTable,
  className,
}: ReportFactTableProps) {
  const facts = factTable.facts ?? []

  if (facts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No facts in this report.</p>
    )
  }

  const hasBothSources =
    facts.some((f) => sourceOf(f.citation.module) === 'sitreps') &&
    facts.some((f) => sourceOf(f.citation.module) === 'survey123')

  return (
    <div className={cn('space-y-4', className)}>
      {/* Shown only when both sources are present, which is when the distinction
          is load-bearing — a single-source report needs no key. */}
      {hasBothSources ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <SourceBadge module="sitreps" />
            corporations&rsquo; signed-off figures
          </span>
          <span className="flex items-center gap-1.5">
            <SourceBadge module="survey123" />
            unverified field observation
          </span>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[72px]">CID</TableHead>
              <TableHead className="w-[84px]">Source</TableHead>
              <TableHead>Metric</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Verification</TableHead>
              <TableHead>Description</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {facts.map((fact) => {
              const cid = fact.citation?.cid
              if (!cid) return null

              return (
                <TableRow
                  key={cid}
                  id={citationAnchorId(cid)}
                  className="scroll-mt-24 transition-colors"
                >
                  {/* The leading edge carries the source, and it lives on the
                      first cell rather than the row. The table sets
                      border-collapse: collapse, where a border declared on a
                      <tr> collapses against the cell grid and paints behind the
                      first cell — measured at zero visual width. Cell borders
                      resolve predictably against the table edge. */}
                  <TableCell
                    className={cn(
                      'border-l-4 font-mono text-xs font-medium',
                      sourceEdgeClass(fact.citation.module),
                    )}
                  >
                    {cid}
                  </TableCell>
                  <TableCell>
                    <SourceBadge module={fact.citation.module} />
                  </TableCell>
                  <TableCell className="font-medium">{fact.metric}</TableCell>
                  <TableCell className="tabular-nums">
                    {formatValue(fact)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{fact.verification}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[240px] text-muted-foreground">
                    {fact.citation.description}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {facts.some((f) => f.breakdown && Object.keys(f.breakdown).length > 0) ? (
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Breakdowns
          </p>
          {facts.map((fact) => {
            if (!fact.breakdown || Object.keys(fact.breakdown).length === 0) {
              return null
            }
            return (
              <div
                key={`${fact.citation.cid}-breakdown`}
                className={cn(
                  'rounded-lg border border-l-4 p-3',
                  sourceEdgeClass(fact.citation.module),
                )}
              >
                <p className="mb-2 flex flex-wrap items-center gap-2 text-sm font-medium">
                  <span className="font-mono text-xs text-primary">
                    {fact.citation.cid}
                  </span>
                  <SourceBadge module={fact.citation.module} />
                  {fact.metric}
                </p>
                <dl className="grid gap-1 text-sm sm:grid-cols-2">
                  {Object.entries(fact.breakdown).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">{key}</dt>
                      <dd className="font-medium tabular-nums">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )
          })}
        </div>
      ) : null}

      {factTable.gaps && factTable.gaps.length > 0 ? (
        <div className="rounded-lg border border-dashed p-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Data gaps
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {factTable.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
