import { useState, type ReactNode } from 'react'

import {
  AS_OF_LABEL,
  SOURCE_QUERY_LABEL,
  formatFactValue,
  formatMetricLabel,
  formatRecordCount,
} from '@/components/reports/citation-display'
import { scrollToCitation } from '@/components/reports/citation-utils'
import {
  SourceBadge,
  sourceLabel,
  sourceOf,
} from '@/components/shared/source-badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import { formatDisplayLabel } from '@/lib/format-display'
import { formatWhen } from '@/lib/format-when'
import { cn } from '@/lib/utils'
import type { Fact } from '@/types/dmcu'

type CitationPopoverProps = {
  fact: Fact
  className?: string
  children: ReactNode
}

export function CitationPopover({
  fact,
  className,
  children,
}: CitationPopoverProps) {
  const [open, setOpen] = useState(false)
  const cid = fact.citation.cid
  const source = sourceOf(fact.citation.module)
  const recordCount = formatRecordCount(fact.citation.record_ids)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        data-source={source}
        title={`${cid} — ${sourceLabel(fact.citation.module)}`}
        className={className}
      >
        {children}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 gap-3 p-3">
        <PopoverHeader>
          <div className="flex items-center gap-2">
            <PopoverTitle className="font-mono text-xs">{cid}</PopoverTitle>
            <SourceBadge module={fact.citation.module} />
          </div>
          <p className="text-base font-semibold tabular-nums">
            {formatFactValue(fact)}
          </p>
          <PopoverDescription>{fact.citation.description}</PopoverDescription>
        </PopoverHeader>

        <p className="text-xs text-muted-foreground">
          {sourceLabel(fact.citation.module)} · {AS_OF_LABEL}{' '}
          {formatWhen(fact.citation.as_of)}
        </p>

        <Collapsible className="rounded-md border">
          <CollapsibleTrigger className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-xs font-medium">
            Technical details
          </CollapsibleTrigger>
          <CollapsibleContent className="border-t px-2.5 py-2">
            <dl className="grid gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Metric</dt>
                <dd className="font-medium">
                  {formatMetricLabel(fact.metric)}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Verification</dt>
                <dd className="font-medium">
                  {formatDisplayLabel(fact.verification)}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">{SOURCE_QUERY_LABEL}</dt>
                <dd>
                  <code className="break-all text-[0.7rem]">
                    {fact.citation.query_ref}
                  </code>
                </dd>
              </div>
              {recordCount ? (
                <div>
                  <dt className="text-muted-foreground">Records</dt>
                  <dd className="font-medium">{recordCount}</dd>
                </div>
              ) : null}
            </dl>
          </CollapsibleContent>
        </Collapsible>

        <Button
          type="button"
          variant="link"
          size="sm"
          className={cn('h-auto self-start px-0')}
          onClick={() => {
            scrollToCitation(cid)
            setOpen(false)
          }}
        >
          View in table
        </Button>
      </PopoverContent>
    </Popover>
  )
}
