import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { CaptureRecord } from '@/components/capture/capture-record'
import { ChatThread } from '@/components/chat/chat-thread'
import { toChatMessages } from '@/components/chat/messages'
import {
  createSseConnection,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { EmptyState, LoadingBlock } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { SubmissionResult } from '@/components/submissions/submission-result'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import {
  captureKeys,
  captureQueries,
  useFileCaptureSession,
  useUpdateCaptureSession,
} from '@/lib/queries/capture'
import { eventQueries } from '@/lib/queries/submissions'
import type {
  CaptureFileResult,
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
      <CorpRoleNotice description="Switch to a corporation identity to file by conversation." />
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
  const fileSession = useFileCaptureSession()
  const navigate = useNavigate()
  const search = Route.useSearch()
  const [filed, setFiled] = useState<CaptureFileResult | null>(null)
  const [sheetOpen, setSheetOpen] = useState(search.open === 'record')

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
  const filedSession = filed?.session ?? session
  const isFiled = filedSession?.status === 'filed'
  const busy = update.isPending || fileSession.isPending

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
  const handleFile = useCallback(() => {
    fileSession.mutate(sessionId, {
      onSuccess: (result) => {
        setFiled(result)
        setSheetOpen(false)
      },
    })
  }, [fileSession, sessionId])
  const handleSave = useCallback(
    (payload: CaptureSessionUpdate) => update.mutate({ id: sessionId, payload }),
    [update, sessionId],
  )

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

  return (
    <div className="-m-4 flex min-h-0 flex-1 flex-col md:-m-6 md:flex-row">
      <main className="order-2 flex min-h-0 flex-1 flex-col px-4 py-4 pb-20 md:order-1 md:px-6 md:pb-4">
        <div className="mx-auto flex w-full min-w-0 max-w-[46rem] flex-1 flex-col gap-4">
          {filed ? (
            <ContentCard title={`Situation Report #${filed.ingest.sequence_no} filed`}>
              <SubmissionResult result={filed.ingest} />
            </ContentCard>
          ) : null}
          <ChatThread
            key={session.id}
            connection={connection}
            initialMessages={initialMessages}
            disabled={isFiled}
            onCustomEvent={onCustomEvent}
            threadId={String(session.id)}
            autoSend={autoSend}
          />
        </div>
      </main>

      <aside className="order-1 hidden shrink-0 md:order-2 md:flex md:sticky md:top-0 md:h-[calc(100svh-3.5rem)] md:w-[400px] md:self-start md:overflow-y-auto md:border-l">
        <CaptureRecord
          session={session}
          events={events}
          disabled={isFiled || busy}
          pending={update.isPending}
          onSave={handleSave}
          onReview={handleFile}
        />
      </aside>

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
            <SheetTitle>Captured record</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <CaptureRecord
              session={session}
              events={events}
              disabled={isFiled || busy}
              pending={update.isPending}
              onSave={handleSave}
              onReview={handleFile}
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
