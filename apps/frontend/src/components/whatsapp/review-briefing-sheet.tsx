import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { formatDisplayValue } from '@/lib/format-display'
import type { DraftIncident, DraftLog, WhatsAppDraft } from '@/types/dmcu'

export const FILE_TO_STORE_WARNING =
  'File to store writes corporation submissions. This is not a signed corp sitrep. Prefer briefing-only unless the DMU is deliberately promoting the hour.'

export function includedAttributedIncidents(draft: WhatsAppDraft): DraftIncident[] {
  return draft.incidents.filter(
    (row) => row.included && row.corporation != null && row.corporation !== '',
  )
}

export function includedAttributedLogs(draft: WhatsAppDraft): DraftLog[] {
  return draft.logs.filter(
    (row) => row.included && row.corporation != null && row.corporation !== '',
  )
}

export function includedAttributedCount(draft: WhatsAppDraft): number {
  return (
    includedAttributedIncidents(draft).length +
    includedAttributedLogs(draft).length
  )
}

export function unattributedRows(draft: WhatsAppDraft): Array<DraftIncident | DraftLog> {
  return [...draft.incidents, ...draft.logs].filter(
    (row) => row.corporation == null || row.corporation === '',
  )
}

export function ReviewBriefingSheet({
  draft,
  open,
  onOpenChange,
  briefingPending,
  promotePending,
  onBrief,
  onPromote,
}: {
  draft: WhatsAppDraft
  open: boolean
  onOpenChange: (open: boolean) => void
  briefingPending: boolean
  promotePending: boolean
  onBrief: () => void
  onPromote: () => void
}) {
  const incidents = includedAttributedIncidents(draft)
  const logs = includedAttributedLogs(draft)
  const includedCount = incidents.length + logs.length
  const missingCorp = unattributedRows(draft)
  const disabled = includedCount === 0 || briefingPending || promotePending

  function handleBrief() {
    onBrief()
    onOpenChange(false)
  }

  function handlePromote() {
    onPromote()
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Review hour briefing</SheetTitle>
          <SheetDescription>
            Check the included rows before generating a provisional briefing or
            filing to the store.
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4">
          {includedCount === 0 ? (
            <p className="text-sm text-muted-foreground">
              Include at least one row with a corporation to brief or file.
            </p>
          ) : (
            <ul className="space-y-3">
              {incidents.map((row) => (
                <li key={`incident-${row.row_id}`} className="text-sm">
                  <p className="font-medium">
                    {row.incident_summary || 'Incident'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDisplayValue(row.corporation)}
                    {row.community ? ` · ${row.community}` : ''}
                  </p>
                </li>
              ))}
              {logs.map((row) => (
                <li key={`log-${row.row_id}`} className="text-sm">
                  <p className="font-medium">{row.statement || 'Log'}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDisplayValue(row.corporation)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {missingCorp.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              {missingCorp.length === 1
                ? '1 row has no corporation and will not appear in the briefing.'
                : `${missingCorp.length} rows have no corporation and will not appear in the briefing.`}
            </p>
          ) : null}
          <p className="text-sm text-muted-foreground">{FILE_TO_STORE_WARNING}</p>
        </div>
        <SheetFooter>
          <Button
            type="button"
            variant="outline"
            disabled={includedCount === 0 || promotePending}
            onClick={handlePromote}
          >
            {promotePending ? 'Filing…' : 'File to store'}
          </Button>
          <Button
            type="button"
            disabled={disabled}
            onClick={handleBrief}
          >
            {briefingPending ? 'Generating…' : 'Generate briefing'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
