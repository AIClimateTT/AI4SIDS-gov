import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { CitationMarkdown } from '@/components/reports'
import { SubmissionResult } from '@/components/submissions/submission-result'
import { useAppForm } from '@/hooks/form'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { isReportJobPending, reportQueries } from '@/lib/queries/reports'
import { formatWhen } from '@/lib/format-when'
import {
  useAdjustWhatsAppDraft,
  useExtractWhatsApp,
  useGenerateWhatsAppBriefing,
  usePromoteWhatsAppDraft,
  useUpdateWhatsAppDraft,
  whatsappQueries,
} from '@/lib/queries/whatsapp'
import type {
  DraftIncident,
  DraftLog,
  SubmissionIngestResult,
  WhatsAppBriefingResult,
} from '@/types/dmcu'

type WhatsAppSearch = { draft?: number }

export const Route = createFileRoute('/dmu/whatsapp')({
  validateSearch: (search: Record<string, unknown>): WhatsAppSearch => {
    const raw = search.draft
    const value =
      typeof raw === 'string' ? Number(raw) : typeof raw === 'number' ? raw : NaN
    return Number.isInteger(value) && value > 0 ? { draft: value } : {}
  },
  component: WhatsAppPage,
})

const LOG_CATEGORIES = [
  'resource',
  'personnel',
  'facility',
  'activity',
  'relief_distributed',
  'other',
] as const

const uploadSchema = z.object({
  as_at: z.string().min(1, 'As at is required'),
  file: z.instanceof(File, { message: 'Choose a WhatsApp .txt export' }),
})

function nowDatetimeLocal(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(
    now.getHours(),
  )}:${pad(now.getMinutes())}`
}

function toIsoDateTime(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}

function hasCorporation(corporation: string | null): boolean {
  return corporation != null && corporation !== ''
}

function WhatsAppPage() {
  const { draft: draftId } = Route.useSearch()
  const navigate = useNavigate()

  if (draftId) {
    return <DraftWorkspace draftId={draftId} />
  }

  return <UploadView onOpened={(id) => {
    void navigate({ to: '/dmu/whatsapp', search: { draft: id } })
  }} />
}

function UploadView({ onOpened }: { onOpened: (id: number) => void }) {
  const extract = useExtractWhatsApp()
  const draftsQuery = useQuery(whatsappQueries.list())

  const form = useAppForm({
    defaultValues: {
      as_at: nowDatetimeLocal(),
      file: undefined as File | undefined,
    },
    validators: {
      onSubmit: uploadSchema,
    },
    onSubmit: async ({ value }) => {
      if (!value.file) return
      const extracted = await extract.mutateAsync({
        file: value.file,
        asAt: toIsoDateTime(value.as_at),
      })
      onOpened(extracted.id)
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="WhatsApp hour"
        description="Extract a group chat into a draft, adjust it, then generate a provisional briefing for the minister."
      />
      <RoleMismatchNotice expected="dmu" />

      {draftsQuery.data && draftsQuery.data.length > 0 ? (
        <ContentCard
          title="Recent drafts"
          description="Resume a working set instead of uploading again."
        >
          <ul className="space-y-2">
            {draftsQuery.data.map((item) => (
              <li key={item.id}>
                <Button
                  variant="ghost"
                  className="h-auto w-full justify-start px-2 py-2 text-left"
                  onClick={() => onOpened(item.id)}
                >
                  <span className="flex w-full flex-col">
                    <span className="text-sm font-medium">{item.filename}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.incident_count} incidents · {item.log_count} logs ·{' '}
                      {formatWhen(item.updated_at)}
                    </span>
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        </ContentCard>
      ) : null}

      <ContentCard
        title="Upload export"
        description="WhatsApp → Chat → Export chat → Without media. A .txt file."
      >
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void form.handleSubmit()
          }}
        >
          <form.AppForm>
            <form.AppField name="as_at">
              {(field) => (
                <field.TextField label="As at" type="datetime-local" required />
              )}
            </form.AppField>
            <form.AppField name="file">
              {(field) => (
                <field.FileField label="WhatsApp export" accept=".txt,text/plain" />
              )}
            </form.AppField>
            <div className="flex justify-end">
              <form.SubmitButton label="Extract" />
            </div>
          </form.AppForm>
        </form>
        {extract.isError ? (
          <p className="mt-4 text-sm text-destructive">{extract.error.message}</p>
        ) : null}
      </ContentCard>
    </div>
  )
}

function DraftWorkspace({ draftId }: { draftId: number }) {
  const navigate = useNavigate()
  const draftQuery = useQuery(whatsappQueries.draft(draftId))
  const updateDraft = useUpdateWhatsAppDraft()
  const adjust = useAdjustWhatsAppDraft()
  const briefing = useGenerateWhatsAppBriefing()
  const promote = usePromoteWhatsAppDraft()

  const [incidents, setIncidents] = useState<DraftIncident[]>([])
  const [logs, setLogs] = useState<DraftLog[]>([])
  const [instruction, setInstruction] = useState('')
  const [briefingResult, setBriefingResult] = useState<WhatsAppBriefingResult | null>(
    null,
  )
  const briefingReport = useQuery(
    reportQueries.detail(briefingResult?.id ?? ''),
  )
  const briefingPending =
    briefing.isPending ||
    isReportJobPending(briefingReport.data?.status ?? briefingResult?.status)
  const [promoteResults, setPromoteResults] = useState<SubmissionIngestResult[] | null>(
    null,
  )
  const dirty = useRef(false)
  const skipSave = useRef(true)
  const saveDraft = updateDraft.mutate

  useEffect(() => {
    if (!draftQuery.data) return
    if (dirty.current) return
    setIncidents(draftQuery.data.incidents)
    setLogs(draftQuery.data.logs)
    skipSave.current = true
  }, [draftQuery.data])

  useEffect(() => {
    if (skipSave.current) {
      skipSave.current = false
      return
    }
    dirty.current = true
    const handle = window.setTimeout(() => {
      if (!dirty.current) return
      dirty.current = false
      saveDraft({
        id: draftId,
        payload: { incidents, logs },
      })
    }, 500)
    return () => window.clearTimeout(handle)
  }, [draftId, incidents, logs, saveDraft])

  const includedCount =
    incidents.filter((row) => row.included && hasCorporation(row.corporation)).length +
    logs.filter((row) => row.included && hasCorporation(row.corporation)).length

  async function handleAdjust() {
    dirty.current = false
    await updateDraft.mutateAsync({ id: draftId, payload: { incidents, logs } })
    await adjust.mutateAsync({ id: draftId, instruction })
    setInstruction('')
  }

  async function handleBriefing() {
    dirty.current = false
    await updateDraft.mutateAsync({ id: draftId, payload: { incidents, logs } })
    const result = await briefing.mutateAsync(draftId)
    setBriefingResult(result)
  }

  async function handlePromote() {
    dirty.current = false
    await updateDraft.mutateAsync({ id: draftId, payload: { incidents, logs } })
    const result = await promote.mutateAsync(draftId)
    setPromoteResults(result.submissions)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="WhatsApp hour"
        description="Adjust the extract, generate a provisional briefing, and file to the store later if needed."
        actions={
          <Button
            variant="outline"
            onClick={() => void navigate({ to: '/dmu/whatsapp', search: {} })}
          >
            New extract
          </Button>
        }
      />
      <RoleMismatchNotice expected="dmu" />

      {draftQuery.isPending ? <LoadingBlock rows={6} /> : null}
      {draftQuery.isError ? (
        <EmptyState
          title="Could not load draft"
          description={draftQuery.error.message}
        />
      ) : null}

      {draftQuery.data ? (
        <>
          <ContentCard
            title={draftQuery.data.filename}
            description={`${draftQuery.data.message_count} messages parsed. Attributed rows are included in the briefing unless you drop them.`}
          >
            {draftQuery.data.pii_redacted ? (
              <p className="mb-4 text-sm text-muted-foreground">
                Phone numbers in the export were redacted before extraction.
              </p>
            ) : null}

            <div className="mb-6 space-y-2">
              <Label htmlFor="whatsapp-adjust">Adjust extraction</Label>
              <Textarea
                id="whatsapp-adjust"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="e.g. Diego Martin, not Siparia. Drop yesterday’s sandbags. Use 5 houses not 3."
              />
              <div className="flex justify-end">
                <Button
                  variant="secondary"
                  disabled={!instruction.trim() || adjust.isPending}
                  onClick={() => void handleAdjust()}
                >
                  {adjust.isPending ? 'Adjusting…' : 'Apply'}
                </Button>
              </div>
            </div>

            {incidents.length === 0 && logs.length === 0 ? (
              <EmptyState
                title="Nothing operational was proposed"
                description="Ask for an adjustment, or upload a different export."
              />
            ) : (
              <div className="space-y-8">
                {incidents.length > 0 ? (
                  <section className="space-y-3">
                    <h2 className="text-sm font-medium">Incidents</h2>
                    {incidents.map((row, index) => (
                      <IncidentCard
                        key={`incident-${row.source_index}-${index}`}
                        row={row}
                        onChange={(next) =>
                          setIncidents(
                            incidents.map((item, itemIndex) =>
                              itemIndex === index ? next : item,
                            ),
                          )
                        }
                      />
                    ))}
                  </section>
                ) : null}
                {logs.length > 0 ? (
                  <section className="space-y-3">
                    <h2 className="text-sm font-medium">Situation logs</h2>
                    {logs.map((row, index) => (
                      <LogCard
                        key={`log-${row.source_index}-${index}`}
                        row={row}
                        onChange={(next) =>
                          setLogs(
                            logs.map((item, itemIndex) =>
                              itemIndex === index ? next : item,
                            ),
                          )
                        }
                      />
                    ))}
                  </section>
                ) : null}
              </div>
            )}
          </ContentCard>

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button
              variant="outline"
              disabled={includedCount === 0 || promote.isPending}
              onClick={() => void handlePromote()}
            >
              {promote.isPending ? 'Filing…' : 'File to store'}
            </Button>
            <Button
              disabled={includedCount === 0 || briefingPending}
              onClick={() => void handleBriefing()}
            >
              {briefingPending ? 'Generating…' : 'Generate briefing'}
            </Button>
          </div>
          <p className="text-right text-xs text-muted-foreground">
            File to store is optional. It writes corporation submissions after you have
            time to review. The briefing does not wait for that.
          </p>
          {adjust.isError ? (
            <p className="text-sm text-destructive">{adjust.error.message}</p>
          ) : null}
          {briefing.isError ? (
            <p className="text-sm text-destructive">{briefing.error.message}</p>
          ) : null}
          {promote.isError ? (
            <p className="text-sm text-destructive">{promote.error.message}</p>
          ) : null}

          {briefingResult ? (
            <ContentCard
              title="Provisional briefing"
              description="Saved as a report. This is not a cited national SITREP."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  render={
                    <Link
                      to="/dmu/reports/$reportId"
                      params={{ reportId: briefingResult.id }}
                    />
                  }
                >
                  Open report
                </Button>
              }
            >
              {briefingPending ? (
                <p className="text-sm text-muted-foreground">Generating briefing…</p>
              ) : (briefingReport.data?.status ?? briefingResult.status) === 'failed' ? (
                <p className="text-sm text-destructive">
                  {briefingReport.data?.error ?? 'Briefing generation failed.'}
                </p>
              ) : (
                <CitationMarkdown
                  markdown={
                    briefingReport.data?.markdown || briefingResult.markdown
                  }
                />
              )}
            </ContentCard>
          ) : null}

          {promoteResults ? (
            <ContentCard title="Filed to store">
              <div className="space-y-4">
                {promoteResults.map((result) => (
                  <SubmissionResult key={result.submission_id} result={result} />
                ))}
              </div>
            </ContentCard>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

function CorporationSelect({
  id,
  value,
  onChange,
}: {
  id: string
  value: string | null
  onChange: (value: string | null) => void
}) {
  return (
    <select
      id={id}
      className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
      value={value ?? ''}
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
  onChange,
}: {
  row: DraftIncident
  onChange: (row: DraftIncident) => void
}) {
  const selectable = hasCorporation(row.corporation)
  const checkId = `incident-include-${row.source_index}`

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkId}
          checked={row.included}
          disabled={!selectable}
          aria-label="Include this incident"
          onCheckedChange={(value) => {
            if (!selectable) return
            onChange({ ...row, included: value === true })
          }}
        />
        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`incident-corp-${row.source_index}`}>Corporation</Label>
            <CorporationSelect
              id={`incident-corp-${row.source_index}`}
              value={row.corporation}
              onChange={(corporation) =>
                onChange({
                  ...row,
                  corporation,
                  included: corporation ? true : false,
                })
              }
            />
            {!selectable ? (
              <p className="text-xs text-muted-foreground">
                Assign a corporation to include this row.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-community-${row.source_index}`}>Community</Label>
            <Input
              id={`incident-community-${row.source_index}`}
              value={row.community ?? ''}
              onChange={(event) =>
                onChange({ ...row, community: event.target.value || null })
              }
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`incident-summary-${row.source_index}`}>Summary</Label>
            <Textarea
              id={`incident-summary-${row.source_index}`}
              value={row.incident_summary}
              onChange={(event) =>
                onChange({ ...row, incident_summary: event.target.value })
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-injuries-${row.source_index}`}>Injuries</Label>
            <Input
              id={`incident-injuries-${row.source_index}`}
              type="number"
              min={0}
              value={row.injuries_count ?? ''}
              onChange={(event) =>
                onChange({
                  ...row,
                  injuries_count: parseOptionalInt(event.target.value),
                })
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`incident-deaths-${row.source_index}`}>Deaths</Label>
            <Input
              id={`incident-deaths-${row.source_index}`}
              type="number"
              min={0}
              value={row.deaths_count ?? ''}
              onChange={(event) =>
                onChange({
                  ...row,
                  deaths_count: parseOptionalInt(event.target.value),
                })
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
  onChange,
}: {
  row: DraftLog
  onChange: (row: DraftLog) => void
}) {
  const selectable = hasCorporation(row.corporation)
  const checkId = `log-include-${row.source_index}`

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkId}
          checked={row.included}
          disabled={!selectable}
          aria-label="Include this log"
          onCheckedChange={(value) => {
            if (!selectable) return
            onChange({ ...row, included: value === true })
          }}
        />
        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor={`log-corp-${row.source_index}`}>Corporation</Label>
            <CorporationSelect
              id={`log-corp-${row.source_index}`}
              value={row.corporation}
              onChange={(corporation) =>
                onChange({
                  ...row,
                  corporation,
                  included: corporation ? true : false,
                })
              }
            />
            {!selectable ? (
              <p className="text-xs text-muted-foreground">
                Assign a corporation to include this row.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <Label htmlFor={`log-category-${row.source_index}`}>Category</Label>
            <select
              id={`log-category-${row.source_index}`}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
              value={row.category}
              onChange={(event) => onChange({ ...row, category: event.target.value })}
            >
              {LOG_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`log-statement-${row.source_index}`}>Statement</Label>
            <Textarea
              id={`log-statement-${row.source_index}`}
              value={row.statement}
              onChange={(event) => onChange({ ...row, statement: event.target.value })}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`log-item-${row.source_index}`}>Item</Label>
            <Input
              id={`log-item-${row.source_index}`}
              value={row.item ?? ''}
              onChange={(event) =>
                onChange({ ...row, item: event.target.value || null })
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor={`log-qty-${row.source_index}`}>Quantity</Label>
              <Input
                id={`log-qty-${row.source_index}`}
                type="number"
                value={row.quantity ?? ''}
                onChange={(event) =>
                  onChange({
                    ...row,
                    quantity: parseOptionalNumber(event.target.value),
                  })
                }
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`log-unit-${row.source_index}`}>Unit</Label>
              <Input
                id={`log-unit-${row.source_index}`}
                value={row.unit ?? ''}
                onChange={(event) =>
                  onChange({ ...row, unit: event.target.value || null })
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
