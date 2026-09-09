import {
  Outlet,
  createRootRouteWithContext,
  useRouterState,
} from '@tanstack/react-router'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { TanStackDevtools } from '@tanstack/react-devtools'
import type { QueryClient } from '@tanstack/react-query'

import { AppSidebar } from '@/components/app-sidebar'
import { CorpSidebar } from '@/components/corp/corp-sidebar'
import { IdentityBadge } from '@/components/identity/identity-badge'
import { IdentityProvider, useIdentity } from '@/hooks/use-identity'
import { AuthProvider } from '@/lib/auth/auth-context'
import { isDmuWorkspace } from '@/lib/identity'
import { useCorpChatWorkspace } from '@/hooks/use-corp-chat-workspace'
import { Separator } from '@/components/ui/separator'
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'

import '../styles.css'

export type RouterContext = {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
})

function RootComponent() {
  return (
    <AuthProvider>
      <IdentityProvider>
        <AppShell />
      </IdentityProvider>
    </AuthProvider>
  )
}

function AppShell() {
  const { identity } = useIdentity()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isCorp = identity?.role === 'corp'
  const isCorpChat = isCorp && pathname.startsWith('/corp/c/')
  const showSidebar = isDmuWorkspace(identity) || isCorp
  const { eventTitle } = useCorpChatWorkspace()
  const isAuthShell =
    pathname === '/login' ||
    pathname === '/verify' ||
    pathname === '/system-unavailable'

  // The print view is the document alone — no sidebar, header, or devtools,
  // so what the browser puts on the page is only the filing.
  if (pathname.startsWith('/corp/print/')) {
    return <Outlet />
  }

  if (isAuthShell) {
    return (
      <TooltipProvider>
        <Outlet />
        <Toaster />
      </TooltipProvider>
    )
  }

  return (
    <TooltipProvider>
      <SidebarProvider className="h-svh overflow-hidden">
        {isDmuWorkspace(identity) ? <AppSidebar /> : null}
        {isCorp ? <CorpSidebar /> : null}
        <SidebarInset className="min-h-0 overflow-hidden">
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            {showSidebar ? (
              <>
                <SidebarTrigger className="-ml-1" />
                <div>
                  <Separator
                    orientation="vertical"
                    className="mr-2 data-[orientation=vertical]:h-4"
                  />
                </div>
              </>
            ) : (
              <span className="text-sm font-medium">DMCU Reports</span>
            )}
            {isCorpChat ? (
              <span className="min-w-0 truncate text-sm font-medium">
                {eventTitle ?? 'New sitrep'}
              </span>
            ) : null}
            {isCorp ? null : <IdentityBadge />}
          </header>
          <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4 md:p-6">
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
      <Toaster />
      <TanStackDevtools
        config={{
          position: 'bottom-right',
        }}
        plugins={[
          {
            name: 'TanStack Router',
            render: <TanStackRouterDevtoolsPanel />,
          },
        ]}
      />
    </TooltipProvider>
  )
}
