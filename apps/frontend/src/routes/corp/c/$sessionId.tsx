import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'

import { CaptureRecord } from '@/components/capture/capture-record'
import { EventConfirmBanner } from '@/components/capture/event-confirm-banner'
import { SitrepDraftPane } from '@/components/capture/sitrep-draft-pane'
import { ChatThread } from '@/components/chat/chat-thread'
import { toChatMessages } from '@/components/chat/messages'
import {
  createSseConnection,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { EmptyState, LoadingBlock } from '@/components/shared'
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
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import {
  captureKeys,
  captureQueries,
  useImportCaptureCsv,
  useIssueCaptureSession,
  usePreviewCaptureSession,
  useUpdateCaptureSession,
} from '@/lib/queries/capture'
import { eventQueries } from '@/lib/queries/submissions'
import type {
  CaptureSession,
  CaptureSessionUpdate,
  EventSummary,
} from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

type SessionSearch = {
  /** The text typed into the home composer, sent as this session's opening
   * turn then stripped from the URL so a refresh never resends it. */
  first?: string
  /** Set by "Add an incident manually" so the mobile sheet opens straight
   * to the record instead of the empty thread. */
  open?: 'record'
}

const DESKTOP_SPLIT = '(min-width: 768px)'

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

export const Route = createFileRoute('/corp/c/$sessionId')({
  validateSearch: (search: Record<string, unknown>): SessionSearch => ({
    first: typeof search.first === 'string' ? search.first : undefined,
    open: search.open === 'record' ? 'record' : undefined,
  }),
  component: CaptureChatRoute,
})

function CaptureChatRoute() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="This account is not a corporation account, so it cannot file by conversation." />
    )
  }

  return <CaptureChatWorkspace identity={identity} />
}

function CaptureChatWorkspace({ identity }: { identity: CorpIdentity }) {
  const { sessionId } = Route.useParams()
  const sessionIdNum = Number(sessionId)
  const eventsQuery = useQuery(eventQueries.list(identity.corporation))

  return (
    <CaptureChatSession
      sessionId={sessionIdNum}
      events={eventsQuery.data ?? []}
    />
  )
}

function CaptureChatSession({
  sessionId,
  events,
}: {
  sessionId: number
  events: EventSummary[]
}) {
  const sessionQuery = useQuery(captureQueries.detail(sessionId))
  const queryClient = useQueryClient()
  const update = useUpdateCaptureSession()
  const navigate = useNavigate()
  const search = Route.useSearch()
  const [sheetOpen, setSheetOpen] = useState(search.open === 'record')
  const isDesktop = useDesktopSplit()
  const preview = usePreviewCaptureSession()
  const issue = useIssueCaptureSession()
  const importCsv = useImportCaptureCsv()

  // Captured once on mount, then the search param is stripped so a reload
  // never resends the opening turn (F6's handoff from the home composer).
  const [autoSend] = useState(() => search.first)

  useEffect(() => {
    if (!search.first && !search.open) return
    void navigate({
      to: '/corp/c/$sessionId',
      params: { sessionId: String(sessionId) },
      search: {},
      replace: true,
    })
    // Runs once, on mount, to consume whatever the URL arrived with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const session = sessionQuery.data
  const isFiled = session?.status === 'filed'
  const busy = update.isPending
  const eventTitle = events.find((event) => event.id === session?.event_id)?.title

  const connection = useMemo(
    () =>
      createSseConnection(`/capture/sessions/${sessionId}/turns/stream`, {
        session_id: sessionId,
      }),
    [sessionId],
  )
  const initialMessages = useMemo(
    () => toChatMessages(session?.messages ?? []),
    [session?.id],
  )
  const onCustomEvent = useCallback(
    (event: ChatCustomEvent) => {
      if (event.name !== 'capture.updated') return
      queryClient.setQueryData(
        captureKeys.detail(sessionId),
        event.value as CaptureSession,
      )
    },
    [queryClient, sessionId],
  )
  const handleSave = useCallback(
    (payload: CaptureSessionUpdate) => update.mutate({ id: sessionId, payload }),
    [update, sessionId],
  )
  const handlePreview = useCallback(
    () => preview.mutate(sessionId),
    [preview, sessionId],
  )
  const handleIssue = useCallback(
    () => issue.mutate(sessionId),
    [issue, sessionId],
  )
  const handleDownloadPdf = useCallback(() => {
    // A separate tab so the officer keeps their place in the conversation;
    // ?auto=true opens the browser's print dialog on arrival.
    window.open(`/corp/print/${sessionId}?auto=true`, '_blank', 'noopener')
  }, [sessionId])

  if (sessionQuery.isError) {
    return (
      <EmptyState
        title="Could not load conversation"
        description={sessionQuery.error.message}
      />
    )
  }

  if (!session) {
    return <LoadingBlock rows={8} />
  }

  const thread = (
    <ChatThread
      key={session.id}
      connection={connection}
      initialMessages={initialMessages}
      disabled={isFiled || importCsv.isPending}
      onCustomEvent={onCustomEvent}
      threadId={String(session.id)}
      autoSend={autoSend}
      banner={
        session.event_id == null && !isFiled ? (
          <EventConfirmBanner
            session={session}
            events={events}
            disabled={busy}
          />
        ) : null
      }
      actions={[
        {
          label: 'Upload incidents CSV',
          accept: '.csv,text/csv',
          onFile: (file) =>
            importCsv.mutate({ id: session.id, kind: 'incidents', file }),
        },
        {
          label: 'Upload situation logs CSV',
          accept: '.csv,text/csv',
          onFile: (file) =>
            importCsv.mutate({ id: session.id, kind: 'logs', file }),
        },
      ]}
    />
  )

  return (
    <div className="-m-4 flex min-h-0 flex-1 flex-col overflow-hidden bg-muted/40 md:-m-6">
      {isDesktop ? (
        <ResizablePanelGroup
          orientation="horizontal"
          className="min-h-0 flex-1"
        >
          <ResizablePanel defaultSize="50%" minSize="32%" className="min-h-0">
            <main className="flex h-full min-h-0 flex-col px-4 py-4 md:px-6">
              {thread}
            </main>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize="50%" minSize="32%" className="min-h-0">
            <div className="m-2 flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-background shadow-sm">
              <ArtifactPane
                session={session}
                events={events}
                eventTitle={eventTitle}
                disabled={isFiled || busy}
                pending={update.isPending}
                previewPending={preview.isPending}
                issuePending={issue.isPending}
                onSave={handleSave}
                onPreview={handlePreview}
                onIssue={handleIssue}
                onDownloadPdf={handleDownloadPdf}
              />
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
          {session.incidents.length} incidents · {session.logs.length} logs
        </span>
        <span className="font-medium text-primary">View record</span>
      </button>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="bottom" className="flex h-[85svh] flex-col gap-0 p-0">
          <SheetHeader className="border-b">
            <SheetTitle className="truncate" title={eventTitle ?? undefined}>
              {eventTitle ?? 'Sitrep'}
            </SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <ArtifactPane
              session={session}
              events={events}
              eventTitle={eventTitle}
              disabled={isFiled || busy}
              pending={update.isPending}
              previewPending={preview.isPending}
              issuePending={issue.isPending}
              onSave={handleSave}
              onPreview={handlePreview}
              onIssue={handleIssue}
              onDownloadPdf={handleDownloadPdf}
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

function ArtifactPane({
  session,
  events,
  eventTitle,
  disabled,
  pending,
  previewPending,
  issuePending,
  onSave,
  onPreview,
  onIssue,
  onDownloadPdf,
}: {
  session: CaptureSession
  events: EventSummary[]
  eventTitle?: string | null
  disabled: boolean
  pending: boolean
  previewPending: boolean
  issuePending: boolean
  onSave: (payload: CaptureSessionUpdate) => void
  onPreview: () => void
  onIssue: () => void
  onDownloadPdf: () => void
}) {
  const autoPreviewedFor = useRef<number | null>(null)

  function handleTabChange(value: unknown) {
    if (value !== 'sitrep') return
    if (autoPreviewedFor.current === session.id) return
    if (session.status !== 'draft') return
    if (session.sitrep != null && !session.sitrep.stale) return
    autoPreviewedFor.current = session.id
    onPreview()
  }

  return (
    <Tabs
      defaultValue="facts"
      className="flex h-full min-h-0 flex-col gap-0"
      onValueChange={handleTabChange}
    >
      <div className="flex shrink-0 items-center border-b px-3 py-2">
        <TabsList variant="line">
          <TabsTrigger value="facts">Facts</TabsTrigger>
          <TabsTrigger value="sitrep">Sitrep</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="facts" className="min-h-0 overflow-hidden">
        <CaptureRecord
          session={session}
          events={events}
          disabled={disabled}
          pending={pending}
          onSave={onSave}
        />
      </TabsContent>
      <TabsContent value="sitrep" className="min-h-0 overflow-hidden">
        <SitrepDraftPane
          session={session}
          eventTitle={eventTitle}
          onPreview={onPreview}
          onIssue={onIssue}
          onDownloadPdf={onDownloadPdf}
          previewPending={previewPending}
          issuePending={issuePending}
        />
      </TabsContent>
    </Tabs>
  )
}
