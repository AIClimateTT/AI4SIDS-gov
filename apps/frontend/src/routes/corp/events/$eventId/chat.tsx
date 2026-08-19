import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { CapturePane } from '@/components/capture/capture-pane'
import { ChatThread } from '@/components/chat/chat-thread'
import { toChatMessages } from '@/components/chat/messages'
import {
  createSseConnection,
  type ChatCustomEvent,
} from '@/components/chat/use-app-chat'
import { CitationMarkdown } from '@/components/reports'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { SubmissionResult } from '@/components/submissions/submission-result'
import { Button } from '@/components/ui/button'
import { useIdentity } from '@/hooks/use-identity'
import type { Identity } from '@/lib/identity'
import {
  captureKeys,
  captureQueries,
  useCreateCaptureSession,
  useFileCaptureSession,
  useUpdateCaptureSession,
} from '@/lib/queries/capture'
import { eventQueries } from '@/lib/queries/submissions'
import { isReportJobPending, reportQueries, useCreateReport } from '@/lib/queries/reports'
import type { CaptureFileResult, CaptureSession } from '@/types/dmcu'

type CorpIdentity = Extract<Identity, { role: 'corp' }>

export const Route = createFileRoute('/corp/events/$eventId/chat')({
  component: CaptureChatPage,
})

function CaptureChatPage() {
  const { identity } = useIdentity()

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to file by conversation." />
    )
  }

  return <CaptureChatWorkspace identity={identity} />
}

function CaptureChatWorkspace({ identity }: { identity: CorpIdentity }) {
  const { eventId } = Route.useParams()
  const eventIdNum = Number(eventId)
  const eventsQuery = useQuery(eventQueries.list(identity.corporation))
  const listQuery = useQuery(captureQueries.list(identity.corporation, eventIdNum))
  const createSession = useCreateCaptureSession()
  const [sessionId, setSessionId] = useState<number | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (!listQuery.isSuccess || started.current) return
    started.current = true
    const draft = listQuery.data.find((item) => item.status === 'draft')
    if (draft) {
      setSessionId(draft.id)
      return
    }
    createSession.mutate(
      { corporation: identity.corporation, eventId: eventIdNum },
      { onSuccess: (created) => setSessionId(created.id) },
    )
  }, [createSession, eventIdNum, identity.corporation, listQuery.data, listQuery.isSuccess])

  const event = eventsQuery.data?.find((candidate) => candidate.id === eventIdNum)

  if (listQuery.isError || createSession.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title="File by conversation" />
        <EmptyState
          title="Could not start a conversation"
          description={
            listQuery.error?.message ??
            createSession.error?.message ??
            'Unknown error'
          }
        />
      </div>
    )
  }

  if (sessionId == null) {
    return (
      <div className="space-y-6">
        <PageHeader title="File by conversation" />
        <LoadingBlock rows={6} />
      </div>
    )
  }

  return (
    <CaptureChatSession
      eventId={eventId}
      eventTitle={event?.title}
      dateFrom={event?.started_at?.slice(0, 10)}
      corporation={identity.corporation}
      sessionId={sessionId}
    />
  )
}

function CaptureChatSession({
  eventId,
  eventTitle,
  dateFrom,
  corporation,
  sessionId,
}: {
  eventId: string
  eventTitle?: string
  dateFrom?: string
  corporation: string
  sessionId: number
}) {
  const sessionQuery = useQuery(captureQueries.detail(sessionId))
  const queryClient = useQueryClient()
  const update = useUpdateCaptureSession()
  const fileSession = useFileCaptureSession()
  const createReport = useCreateReport()
  const [filed, setFiled] = useState<CaptureFileResult | null>(null)
  const generatedReport = useQuery(
    reportQueries.detail(createReport.data?.id ?? ''),
  )
  const reportPending = isReportJobPending(generatedReport.data?.status)

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
    <div className="-m-4 md:-m-6">
      <div className="flex flex-col items-stretch md:flex-row md:items-start">
        <aside className="flex h-[min(32rem,70svh)] w-full shrink-0 flex-col border-b bg-background md:sticky md:top-0 md:h-[calc(100svh-3.5rem)] md:w-[380px] md:self-start md:border-r md:border-b-0">
          <div className="shrink-0 space-y-2 border-b px-4 py-3">
            <h1 className="text-lg font-semibold tracking-tight">
              File by conversation
            </h1>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                render={<Link to="/corp/events/$eventId" params={{ eventId }} />}
              >
                Back to event
              </Button>
              {!isFiled ? (
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    fileSession.mutate(session.id, {
                      onSuccess: (result) => setFiled(result),
                    })
                  }}
                >
                  File this report
                </Button>
              ) : (
                <Button
                  size="sm"
                  disabled={
                    createReport.isPending || reportPending || !dateFrom
                  }
                  onClick={() => {
                    const dateTo = (filedSession?.as_at ?? session.as_at).slice(0, 10)
                    createReport.mutate({
                      template: 'corp_situation_report',
                      params: {
                        corporation,
                        date_from: dateFrom ?? dateTo,
                        date_to: dateTo,
                      },
                    })
                  }}
                >
                  {createReport.isPending || reportPending
                    ? 'Generating…'
                    : 'Generate situation report'}
                </Button>
              )}
            </div>
          </div>
          <div className="min-h-0 flex-1 px-4 py-3">
            <ChatThread
              key={session.id}
              connection={connection}
              initialMessages={initialMessages}
              disabled={isFiled}
              onCustomEvent={onCustomEvent}
              threadId={String(session.id)}
            />
          </div>
        </aside>
        <div className="min-w-0 flex-1 space-y-4 px-4 py-4 md:px-6">
          {eventTitle ? (
            <p className="text-sm text-muted-foreground">
              Capturing incidents and situation logs for {eventTitle}.
            </p>
          ) : null}

          {filed ? (
            <ContentCard title={`Situation Report #${filed.ingest.sequence_no} filed`}>
              <SubmissionResult result={filed.ingest} />
            </ContentCard>
          ) : null}

          {generatedReport.data && !isReportJobPending(generatedReport.data.status) ? (
            <ContentCard title="Draft situation report">
              {generatedReport.data.status === 'failed' ? (
                <p className="text-sm text-destructive">
                  {generatedReport.data.error ?? 'Report generation failed.'}
                </p>
              ) : (
                <CitationMarkdown markdown={generatedReport.data.markdown} />
              )}
            </ContentCard>
          ) : null}

          <CapturePane
            session={session}
            disabled={isFiled || busy}
            pending={update.isPending}
            onSave={(payload) => update.mutate({ id: session.id, payload })}
          />
        </div>
      </div>
    </div>
  )
}
