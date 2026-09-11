import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { EmptyState } from '@/components/shared'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { formatDisplayLabel } from '@/lib/format-display'
import { toDatetimeLocal, toIsoDateTime } from '@/lib/capture-mapping'
import { incidentPath, logPath, withManual, withManualPaths } from '@/lib/whatsapp-paths'
import type {
  CaptureMissingField,
  DraftIncident,
  DraftLog,
  WhatsAppDraft,
  WhatsAppDraftUpdate,
} from '@/types/dmcu'
import type { ReactNode } from 'react'

const LOG_CATEGORIES = [
  'resource',
  'personnel',
  'facility',
  'activity',
  'relief_distributed',
  'other',
] as const

export type WhatsAppDraftRecordProps = {
  draft: WhatsAppDraft
  disabled?: boolean
  pending?: boolean
  onSave: (payload: WhatsAppDraftUpdate) => void
  footer?: ReactNode
}

function payloadOf(
  draft: WhatsAppDraft,
  patch: Partial<WhatsAppDraftUpdate>,
): WhatsAppDraftUpdate {
  return {
    as_at: patch.as_at ?? draft.as_at,
    incidents: patch.incidents ?? draft.incidents,
    logs: patch.logs ?? draft.logs,
    manual_fields: patch.manual_fields ?? draft.manual_fields,
  }
}

function missingFor(
  missing: CaptureMissingField[],
  path: string,
): CaptureMissingField | undefined {
  return missing.find((item) => item.path === path)
}

function hasCorporation(corporation: string | null): boolean {
  return corporation != null && corporation !== ''
}

export function WhatsAppDraftRecord({
  draft,
  disabled,
  pending,
  onSave,
  footer,
}: WhatsAppDraftRecordProps) {
  const asAtMissing = missingFor(draft.missing, 'as_at')

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
        <div className="space-y-1">
          <Label htmlFor="whatsapp-as-at-chip" className="text-xs">
            As at
          </Label>
          <Input
            id="whatsapp-as-at-chip"
            type="datetime-local"
            className="h-8 w-[13.5rem]"
            value={toDatetimeLocal(draft.as_at)}
            disabled={disabled}
            aria-invalid={asAtMissing ? true : undefined}
            onChange={(event) =>
              onSave(
                payloadOf(draft, {
                  as_at: toIsoDateTime(event.target.value),
                  manual_fields: withManual(draft.manual_fields, 'as_at'),
                }),
              )
            }
          />
        </div>
        {pending ? (
          <p className="text-xs text-muted-foreground">Saving…</p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {draft.incidents.length === 0 && draft.logs.length === 0 ? (
          <EmptyState
            title="Nothing operational was proposed"
            description="Ask in the thread, or start from different context."
          />
        ) : (
          <>
            {draft.incidents.length > 0 ? (
              <section className="space-y-3">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  Incidents
                </h2>
                {draft.incidents.map((row, index) => (
                  <IncidentCard
                    key={row.row_id}
                    row={row}
                    missing={draft.missing}
                    disabled={disabled}
                    onChange={(next, paths) =>
                      onSave(
                        payloadOf(draft, {
                          incidents: draft.incidents.map((item, itemIndex) =>
                            itemIndex === index ? next : item,
                          ),
                          manual_fields: withManualPaths(draft.manual_fields, paths),
                        }),
                      )
                    }
                  />
                ))}
              </section>
            ) : null}
            {draft.logs.length > 0 ? (
              <section className="space-y-3">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  Situation logs
                </h2>
                {draft.logs.map((row, index) => (
                  <LogCard
                    key={row.row_id}
                    row={row}
                    missing={draft.missing}
                    disabled={disabled}
                    onChange={(next, paths) =>
                      onSave(
                        payloadOf(draft, {
                          logs: draft.logs.map((item, itemIndex) =>
                            itemIndex === index ? next : item,
                          ),
                          manual_fields: withManualPaths(draft.manual_fields, paths),
                        }),
                      )
                    }
                  />
                ))}
              </section>
            ) : null}
          </>
        )}
      </div>
      {footer ? (
        <div className="shrink-0 space-y-2 border-t px-4 py-3">{footer}</div>
      ) : null}
    </div>
  )
}

function CorporationSelect({
  id,
  value,
  onChange,
  disabled,
}: {
  id: string
  value: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
}) {
  return (
    <select
      id={id}
      className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
      value={value ?? ''}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">Assign corporation</option>
      {CORPORATION_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

function IncidentCard({
  row,
  missing,
  disabled,
  onChange,
}: {
  row: DraftIncident
  missing: CaptureMissingField[]
  disabled?: boolean
  onChange: (row: DraftIncident, paths: string[]) => void
}) {
  const selectable = hasCorporation(row.corporation)
  const checkId = `incident-include-${row.row_id}`
  const corpMissing = missingFor(missing, incidentPath(row.row_id, 'corporation'))
  const summaryMissing = missingFor(
    missing,
    incidentPath(row.row_id, 'incident_summary'),
  )

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkId}
          checked={row.included}
          disabled={disabled || !selectable}
          aria-label="Include this incident"
          onCheckedChange={(value) => {
            if (!selectable) return
            onChange({ ...row, included: value === true }, [
              incidentPath(row.row_id, 'included'),
            ])
          }}
        />
        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`incident-corp-${row.row_id}`}>Corporation</Label>
            <CorporationSelect
              id={`incident-corp-${row.row_id}`}
              value={row.corporation}
              disabled={disabled}
              onChange={(corporation) =>
                onChange(
                  {
                    ...row,
                    corporation,
                    included: corporation ? true : false,
                  },
                  [
                    incidentPath(row.row_id, 'corporation'),
                    incidentPath(row.row_id, 'included'),
                  ],
                )
              }
            />
            {corpMissing ? (
              <p className="text-xs text-muted-foreground">{corpMissing.message}</p>
            ) : !selectable ? (
              <p className="text-xs text-muted-foreground">
                Assign a corporation to include this row.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-community-${row.row_id}`}>Community</Label>
            <Input
              id={`incident-community-${row.row_id}`}
              value={row.community ?? ''}
              disabled={disabled}
              onChange={(event) =>
                onChange(
                  { ...row, community: event.target.value || null },
                  [incidentPath(row.row_id, 'community')],
                )
              }
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`incident-summary-${row.row_id}`}>Summary</Label>
            <Textarea
              id={`incident-summary-${row.row_id}`}
              value={row.incident_summary}
              disabled={disabled}
              aria-invalid={summaryMissing ? true : undefined}
              onChange={(event) =>
                onChange({ ...row, incident_summary: event.target.value }, [
                  incidentPath(row.row_id, 'incident_summary'),
                ])
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-injuries-${row.row_id}`}>Injuries</Label>
            <Input
              id={`incident-injuries-${row.row_id}`}
              type="number"
              min={0}
              value={row.injuries_count ?? ''}
              disabled={disabled}
              onChange={(event) =>
                onChange(
                  {
                    ...row,
                    injuries_count: parseOptionalInt(event.target.value),
                  },
                  [incidentPath(row.row_id, 'injuries_count')],
                )
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-deaths-${row.row_id}`}>Deaths</Label>
            <Input
              id={`incident-deaths-${row.row_id}`}
              type="number"
              min={0}
              value={row.deaths_count ?? ''}
              disabled={disabled}
              onChange={(event) =>
                onChange(
                  {
                    ...row,
                    deaths_count: parseOptionalInt(event.target.value),
                  },
                  [incidentPath(row.row_id, 'deaths_count')],
                )
              }
            />
          </div>
        </div>
      </div>
      <SourceQuote quote={row.source_quote} index={row.source_index} />
    </div>
  )
}

function LogCard({
  row,
  missing,
  disabled,
  onChange,
}: {
  row: DraftLog
  missing: CaptureMissingField[]
  disabled?: boolean
  onChange: (row: DraftLog, paths: string[]) => void
}) {
  const selectable = hasCorporation(row.corporation)
  const checkId = `log-include-${row.row_id}`
  const corpMissing = missingFor(missing, logPath(row.row_id, 'corporation'))

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkId}
          checked={row.included}
          disabled={disabled || !selectable}
          aria-label="Include this log"
          onCheckedChange={(value) => {
            if (!selectable) return
            onChange({ ...row, included: value === true }, [
              logPath(row.row_id, 'included'),
            ])
          }}
        />
        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`log-corp-${row.row_id}`}>Corporation</Label>
            <CorporationSelect
              id={`log-corp-${row.row_id}`}
              value={row.corporation}
              disabled={disabled}
              onChange={(corporation) =>
                onChange(
                  {
                    ...row,
                    corporation,
                    included: corporation ? true : false,
                  },
                  [logPath(row.row_id, 'corporation'), logPath(row.row_id, 'included')],
                )
              }
            />
            {corpMissing ? (
              <p className="text-xs text-muted-foreground">{corpMissing.message}</p>
            ) : !selectable ? (
              <p className="text-xs text-muted-foreground">
                Assign a corporation to include this row.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <Label htmlFor={`log-category-${row.row_id}`}>Category</Label>
            <select
              id={`log-category-${row.row_id}`}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
              value={row.category}
              disabled={disabled}
              onChange={(event) =>
                onChange({ ...row, category: event.target.value }, [
                  logPath(row.row_id, 'category'),
                ])
              }
            >
              {LOG_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {formatDisplayLabel(category)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`log-statement-${row.row_id}`}>Statement</Label>
            <Textarea
              id={`log-statement-${row.row_id}`}
              value={row.statement}
              disabled={disabled}
              onChange={(event) =>
                onChange({ ...row, statement: event.target.value }, [
                  logPath(row.row_id, 'statement'),
                ])
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`log-item-${row.row_id}`}>Item</Label>
            <Input
              id={`log-item-${row.row_id}`}
              value={row.item ?? ''}
              disabled={disabled}
              onChange={(event) =>
                onChange({ ...row, item: event.target.value || null }, [
                  logPath(row.row_id, 'item'),
                ])
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor={`log-qty-${row.row_id}`}>Quantity</Label>
              <Input
                id={`log-qty-${row.row_id}`}
                type="number"
                value={row.quantity ?? ''}
                disabled={disabled}
                onChange={(event) =>
                  onChange(
                    {
                      ...row,
                      quantity: parseOptionalNumber(event.target.value),
                    },
                    [logPath(row.row_id, 'quantity')],
                  )
                }
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`log-unit-${row.row_id}`}>Unit</Label>
              <Input
                id={`log-unit-${row.row_id}`}
                value={row.unit ?? ''}
                disabled={disabled}
                onChange={(event) =>
                  onChange({ ...row, unit: event.target.value || null }, [
                    logPath(row.row_id, 'unit'),
                  ])
                }
              />
            </div>
          </div>
        </div>
      </div>
      <SourceQuote quote={row.source_quote} index={row.source_index} />
    </div>
  )
}

function SourceQuote({ quote, index }: { quote: string; index: number }) {
  return (
    <p className="text-xs text-muted-foreground">
      Message {index}: “{quote}”
    </p>
  )
}

function parseOptionalInt(raw: string): number | null {
  if (raw.trim() === '') return null
  const value = Number.parseInt(raw, 10)
  return Number.isFinite(value) ? value : null
}

function parseOptionalNumber(raw: string): number | null {
  if (raw.trim() === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}
