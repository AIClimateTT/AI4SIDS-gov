import { Link } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  useCallback,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react'

import { ChatThread } from '@/components/chat/chat-thread'
import { toChatMessages } from '@/components/chat/messages'
import {
  createSseConnection,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'
import {
  RecordFooterActions,
  WhatsAppDraftRecord,
} from '@/components/whatsapp/draft-record'
import { CitationMarkdown } from '@/components/reports'
import { SubmissionResult } from '@/components/submissions/submission-result'
import {
  EmptyState,
  LoadingBlock,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { isReportJobPending, reportQueries } from '@/lib/queries/reports'
import {
  isWhatsAppExtractPending,
  useGenerateWhatsAppBriefing,
  usePromoteWhatsAppDraft,
  useUpdateWhatsAppDraft,
  whatsappKeys,
  whatsappQueries,
} from '@/lib/queries/whatsapp'
import type {
  SubmissionIngestResult,
  WhatsAppBriefingResult,
  WhatsAppDraft,
  WhatsAppDraftUpdate,
} from '@/types/dmcu'

const DESKTOP_SPLIT = '(min-width: 768px)'
const COMPOSER_PLACEHOLDER =
  'Assign a corporation, drop a row, or correct a figure…'

function subscribeDesktop(notify: () => void) {
  const media = window.matchMedia(DESKTOP_SPLIT)
  media.addEventListener('change', notify)
  return () => media.removeEventListener('change', notify)
}

function desktopSnapshot() {
  return window.matchMedia(DESKTOP_SPLIT).matches
}

function useDesktopSplit() {
  return useSyncExternalStore(subscribeDesktop, desktopSnapshot, () => true)
}

function hasCorporation(corporation: string | null): boolean {
  return corporation != null && corporation !== ''
}

export function sourceTitle(draft: {
  filename: string
  source_kind: 'export' | 'paste'
}): string {
  return draft.source_kind === 'paste' ? 'Pasted context' : draft.filename
}

export function WhatsAppDraftWorkspace({
  draftId,
  onNewExtract,
}: {
  draftId: number
  onNewExtract: () => void
}) {
  const draftQuery = useQuery(whatsappQueries.draft(draftId))

  if (draftQuery.isPending) return <LoadingBlock rows={8} />
  if (draftQuery.isError) {
    return (
      <EmptyState
        title="Could not load draft"
        description={draftQuery.error.message}
      />
    )
  }
  if (!draftQuery.data) return <LoadingBlock rows={8} />

  if (isWhatsAppExtractPending(draftQuery.data.status)) {
    return (
      <ContentCard
        title={sourceTitle(draftQuery.data)}
        description="Extracting operational facts from the source…"
      >
        <p className="text-sm text-muted-foreground">Extracting the hour…</p>
      </ContentCard>
    )
  }

  if (draftQuery.data.status === 'failed') {
    return (
      <EmptyState
        title="Extraction failed"
        description={draftQuery.data.error ?? 'The extract job failed.'}
      />
    )
  }

  return (
    <ConversationLayout
      draft={draftQuery.data}
      onNewExtract={onNewExtract}
    />
  )
}

function ConversationLayout({
  draft,
  onNewExtract,
}: {
  draft: WhatsAppDraft
  onNewExtract: () => void
}) {
  const queryClient = useQueryClient()
  const update = useUpdateWhatsAppDraft()
  const briefing = useGenerateWhatsAppBriefing()
  const promote = usePromoteWhatsAppDraft()
  const [sheetOpen, setSheetOpen] = useState(false)
  const isDesktop = useDesktopSplit()
  const [briefingResult, setBriefingResult] =
    useState<WhatsAppBriefingResult | null>(null)
  const briefingReport = useQuery(reportQueries.detail(briefingResult?.id ?? ''))
  const briefingPending =
    briefing.isPending ||
    isReportJobPending(briefingReport.data?.status ?? briefingResult?.status)
  const [promoteResults, setPromoteResults] = useState<
    SubmissionIngestResult[] | null
  >(null)

  const connection = useMemo(
    () =>
      createSseConnection(`/whatsapp/drafts/${draft.id}/turns/stream`, {
        draft_id: draft.id,
      }),
    [draft.id],
  )
  const initialMessages = useMemo(
    () => toChatMessages(draft.messages ?? []),
    [draft.id],
  )
  const onCustomEvent = useCallback(
    (event: ChatCustomEvent) => {
      if (event.name !== 'whatsapp.updated') return
      queryClient.setQueryData(
        whatsappKeys.draft(draft.id),
        event.value as WhatsAppDraft,
      )
    },
    [queryClient, draft.id],
  )
  const handleSave = useCallback(
    (payload: WhatsAppDraftUpdate) => update.mutate({ id: draft.id, payload }),
    [update, draft.id],
  )

  const includedCount =
    draft.incidents.filter((row) => row.included && hasCorporation(row.corporation))
      .length +
    draft.logs.filter((row) => row.included && hasCorporation(row.corporation)).length

  async function handleBriefing() {
    const result = await briefing.mutateAsync(draft.id)
    setBriefingResult(result)
  }

  async function handlePromote() {
    const result = await promote.mutateAsync(draft.id)
    setPromoteResults(result.submissions)
  }

  const recordPane = (
    <WhatsAppDraftRecord
      draft={draft}
      disabled={update.isPending}
      pending={update.isPending}
      onSave={handleSave}
      footer={
        <>
          <RecordFooterActions
            includedCount={includedCount}
            briefingPending={briefingPending}
            promotePending={promote.isPending}
            onBriefing={() => void handleBriefing()}
            onPromote={() => void handlePromote()}
            briefingError={briefing.error?.message}
            promoteError={promote.error?.message}
          />
          {briefingResult ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Provisional briefing — not a cited national SITREP.
              </p>
              {briefingPending ? (
                <p className="text-sm text-muted-foreground">Generating briefing…</p>
              ) : (briefingReport.data?.status ?? briefingResult.status) ===
                'failed' ? (
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
            </div>
          ) : null}
          {promoteResults ? (
            <div className="space-y-4">
              {promoteResults.map((result) => (
                <SubmissionResult key={result.submission_id} result={result} />
              ))}
            </div>
          ) : null}
        </>
      }
    />
  )

  const thread = (
    <ChatThread
      key={draft.id}
      connection={connection}
      initialMessages={initialMessages}
      onCustomEvent={onCustomEvent}
      threadId={String(draft.id)}
      placeholder={COMPOSER_PLACEHOLDER}
      banner={
        draft.pii_redacted ? (
          <p className="text-xs text-muted-foreground">
            Phone numbers in the source were redacted before extraction.
          </p>
        ) : null
      }
    />
  )

  const railHeader = (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2">
      <p className="min-w-0 truncate text-sm font-medium">{sourceTitle(draft)}</p>
      <Button variant="outline" size="sm" onClick={onNewExtract}>
        New extract
      </Button>
    </div>
  )

  return (
    <div className="-m-4 flex min-h-0 flex-1 flex-col overflow-hidden bg-muted/40 md:-m-6">
      {isDesktop ? (
        <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
          <ResizablePanel defaultSize="68%" minSize="40%" className="min-h-0">
            <main className="flex h-full min-h-0 flex-col px-4 py-4 md:px-6">
              {thread}
            </main>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize="32%" minSize="28%" className="min-h-0">
            <div className="m-2 flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-background shadow-sm">
              {railHeader}
              <div className="flex min-h-0 flex-1 flex-col">{recordPane}</div>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      ) : (
        <main className="flex min-h-0 flex-1 flex-col px-4 py-4 pb-20">
          {thread}
        </main>
      )}

      <button
        type="button"
        className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-between border-t bg-background px-4 py-3 text-sm md:hidden"
        onClick={() => setSheetOpen(true)}
      >
        <span>
          {draft.incidents.length} incidents · {draft.logs.length} logs
        </span>
        <span className="font-medium text-primary">View record</span>
      </button>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="bottom" className="flex h-[85svh] flex-col gap-0 p-0">
          <SheetHeader className="border-b">
            <SheetTitle className="truncate">{sourceTitle(draft)}</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex shrink-0 justify-end px-3 py-2">
              <Button variant="outline" size="sm" onClick={onNewExtract}>
                New extract
              </Button>
            </div>
            {recordPane}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export const WHATSAPP_COMPOSER_PLACEHOLDER = COMPOSER_PLACEHOLDER
