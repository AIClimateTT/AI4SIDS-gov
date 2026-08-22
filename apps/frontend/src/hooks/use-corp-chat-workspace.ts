import { useQuery } from '@tanstack/react-query'
import { useRouterState } from '@tanstack/react-router'

import { useIdentity } from '@/hooks/use-identity'
import { captureQueries } from '@/lib/queries/capture'
import { eventQueries } from '@/lib/queries/submissions'

export function useCorpChatSessionId(): number | null {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const match = pathname.match(/^\/corp\/c\/(\d+)/)
  if (!match) return null
  const id = Number(match[1])
  return Number.isInteger(id) && id > 0 ? id : null
}

export function useCorpEventPageId(): number | null {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const match = pathname.match(/^\/corp\/events\/(\d+)/)
  if (!match) return null
  const id = Number(match[1])
  return Number.isInteger(id) && id > 0 ? id : null
}

export function useCorpChatWorkspace() {
  const sessionId = useCorpChatSessionId()
  const { identity } = useIdentity()
  const corporation = identity?.role === 'corp' ? identity.corporation : ''
  const sessionQuery = useQuery(captureQueries.detail(sessionId ?? 0))
  const eventsQuery = useQuery(eventQueries.list(corporation))
  const session = sessionQuery.data
  const eventId = session?.event_id ?? null
  const eventTitle =
    eventsQuery.data?.find((event) => event.id === eventId)?.title ?? null

  return {
    sessionId,
    session,
    eventId,
    eventTitle,
    corporation,
  }
}
