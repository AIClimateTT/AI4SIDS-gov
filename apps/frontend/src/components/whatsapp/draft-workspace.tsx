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
import { WhatsAppBriefingPane } from '@/components/whatsapp/briefing-pane'
import { WhatsAppDraftRecord } from '@/components/whatsapp/draft-record'
import { ReviewBriefingSheet } from '@/components/whatsapp/review-briefing-sheet'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  ReportDetail,
  SubmissionIngestResult,
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
  const [reviewOpen, setReviewOpen] = useState(false)
  const isDesktop = useDesktopSplit()
  const briefingReport = useQuery(
    reportQueries.detail(draft.briefing_report_id ?? ''),
  )
  const briefingPending =
    briefing.isPending ||
    isReportJobPending(briefingReport.data?.status)
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
    await briefing.mutateAsync(draft.id)
  }

  async function handlePromote() {
    const result = await promote.mutateAsync(draft.id)
    setPromoteResults(result.submissions)
  }

  const artifactPane = (
    <ArtifactPane
      draft={draft}
      disabled={update.isPending}
      pending={update.isPending}
      includedCount={includedCount}
      briefingPending={briefingPending}
      promotePending={promote.isPending}
      report={briefingReport.data}
      onSave={handleSave}
      onReview={() => setReviewOpen(true)}
      onPromote={() => void handlePromote()}
      briefingError={briefing.error?.message}
      promoteError={promote.error?.message}
      promoteResults={promoteResults}
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
              {artifactPane}
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
            {artifactPane}
          </div>
        </SheetContent>
      </Sheet>
      <ReviewBriefingSheet
        draft={draft}
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        briefingPending={briefingPending}
        promotePending={promote.isPending}
        onBrief={() => void handleBriefing()}
        onPromote={() => void handlePromote()}
      />
    </div>
  )
}

function ArtifactPane({
  draft,
  disabled,
  pending,
  includedCount,
  briefingPending,
  promotePending,
  report,
  onSave,
  onReview,
  onPromote,
  briefingError,
  promoteError,
  promoteResults,
}: {
  draft: WhatsAppDraft
  disabled: boolean
  pending: boolean
  includedCount: number
  briefingPending: boolean
  promotePending: boolean
  report: ReportDetail | undefined
  onSave: (payload: WhatsAppDraftUpdate) => void
  onReview: () => void
  onPromote: () => void
  briefingError?: string
  promoteError?: string
  promoteResults: SubmissionIngestResult[] | null
}) {
  return (
    <Tabs defaultValue="record" className="flex h-full min-h-0 flex-col gap-0">
      <div className="flex shrink-0 items-center border-b px-3 py-2">
        <TabsList variant="line">
          <TabsTrigger value="record">Record</TabsTrigger>
          <TabsTrigger value="briefing">Briefing</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="record" className="min-h-0 overflow-hidden">
        <WhatsAppDraftRecord
          draft={draft}
          disabled={disabled}
          pending={pending}
          onSave={onSave}
        />
      </TabsContent>
      <TabsContent value="briefing" className="min-h-0 overflow-hidden">
        <WhatsAppBriefingPane
          draft={draft}
          report={report}
          includedCount={includedCount}
          briefingPending={briefingPending}
          promotePending={promotePending}
          onReview={onReview}
          onPromote={onPromote}
          briefingError={briefingError}
          promoteError={promoteError}
          promoteResults={promoteResults}
        />
      </TabsContent>
    </Tabs>
  )
}

export const WHATSAPP_COMPOSER_PLACEHOLDER = COMPOSER_PLACEHOLDER
