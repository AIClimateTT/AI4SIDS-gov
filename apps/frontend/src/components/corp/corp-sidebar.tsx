import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { FileTextIcon, HouseIcon, MapPinIcon } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import {
  useCorpChatWorkspace,
  useCorpEventPageId,
} from '@/hooks/use-corp-chat-workspace'
import { useIdentity } from '@/hooks/use-identity'
import { identityLabel } from '@/lib/identity'
import { captureQueries } from '@/lib/queries/capture'
import { eventQueries } from '@/lib/queries/submissions'
import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

export function CorpSidebar() {
  const { identity, forgetIdentity } = useIdentity()
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const { sessionId, eventId: chatEventId, eventTitle: chatEventTitle, corporation } =
    useCorpChatWorkspace()
  const eventPageId = useCorpEventPageId()
  const eventId = chatEventId ?? eventPageId
  const eventsQuery = useQuery(eventQueries.list(corporation))
  const eventTitle =
    chatEventTitle ??
    eventsQuery.data?.find((event) => event.id === eventId)?.title ??
    null
  const sessionsQuery = useQuery({
    ...captureQueries.list(corporation, eventId ?? 0),
    enabled: !!corporation && eventId != null,
  })

  const sitreps = (sessionsQuery.data ?? [])
    .slice()
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  const otherEvents = (eventsQuery.data ?? []).filter(
    (event) => event.id !== eventId,
  )

  if (identity?.role !== 'corp') return null

  return (
    <Sidebar variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link to="/corp" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <FileTextIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">DMCU Reports</span>
                <span className="truncate text-xs">Situation reports</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Go to</SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="Home"
                isActive={pathname === '/corp' || pathname === '/corp/'}
                render={<Link to="/corp" />}
              >
                <HouseIcon />
                <span>Home</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            {eventId != null ? (
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Event"
                  isActive={pathname.startsWith(`/corp/events/${eventId}`)}
                  render={
                    <Link
                      to="/corp/events/$eventId"
                      params={{ eventId: String(eventId) }}
                    />
                  }
                >
                  <MapPinIcon />
                  <span>Event</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ) : null}
          </SidebarMenu>
        </SidebarGroup>

        {eventId != null ? (
          <SidebarGroup>
            <SidebarGroupLabel>{eventTitle ?? 'This event'}</SidebarGroupLabel>
            <SidebarMenu>
              {sitreps.length === 0 ? (
                <SidebarMenuItem>
                  <SidebarMenuButton disabled>
                    <span>No sitreps yet</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : (
                sitreps.map((sitrep) => (
                  <SidebarMenuItem key={sitrep.id}>
                    <SidebarMenuButton
                      isActive={sitrep.id === sessionId}
                      tooltip={sitrep.status === 'draft' ? 'Draft' : 'Issued'}
                      render={
                        <Link
                          to="/corp/c/$sessionId"
                          params={{ sessionId: String(sitrep.id) }}
                        />
                      }
                    >
                      <span className="truncate">
                        {sitrep.status === 'draft' ? 'Draft' : 'Issued'} ·{' '}
                        {new Date(sitrep.updated_at).toLocaleDateString()}
                      </span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))
              )}
            </SidebarMenu>
          </SidebarGroup>
        ) : null}

        <SidebarGroup>
          <SidebarGroupLabel>
            {eventId != null ? 'Other events' : 'Events'}
          </SidebarGroupLabel>
          <SidebarMenu>
            {otherEvents.length === 0 ? (
              <SidebarMenuItem>
                <SidebarMenuButton disabled>
                  <span>{eventId != null ? 'No other events' : 'No events'}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ) : (
              otherEvents.map((event) => (
                <SidebarMenuItem key={event.id}>
                  <SidebarMenuButton
                    tooltip={event.title}
                    render={
                      <Link
                        to="/corp/events/$eventId"
                        params={{ eventId: String(event.id) }}
                      />
                    }
                  >
                    <span className="truncate">{event.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))
            )}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
            <span className="truncate font-medium">{identityLabel(identity)}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              forgetIdentity()
              void navigate({ to: '/who-are-you' })
            }}
          >
            Switch
          </Button>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
