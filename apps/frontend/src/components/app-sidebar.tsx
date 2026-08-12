import type { ComponentProps } from 'react'
import { Link } from '@tanstack/react-router'
import {
  CalendarIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  BoxesIcon,
  UploadIcon,
} from 'lucide-react'

import { useIdentity } from '@/hooks/use-identity'

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

// "File a report" is deliberately absent: filing happens through an event, and
// a nav item that cannot know which event would have to ask — the picker the
// spec rejects.
const CORP_NAV = [
  { title: 'Events', to: '/corp', icon: CalendarIcon },
  { title: 'My submissions', to: '/corp/submissions', icon: FileTextIcon },
] as const

const DMU_NAV = [
  { title: 'Dashboard', to: '/dmu', icon: LayoutDashboardIcon },
  { title: 'Field data', to: '/dmu/field-data', icon: UploadIcon },
  { title: 'Reports', to: '/dmu/reports', icon: FileTextIcon },
  { title: 'Templates', to: '/dmu/admin/templates', icon: LibraryIcon },
  { title: 'Modules', to: '/dmu/admin/modules', icon: BoxesIcon },
] as const

export function AppSidebar(props: ComponentProps<typeof Sidebar>) {
  const { identity } = useIdentity()
  // No identity means the only reachable page is the who-are-you screen, so an
  // empty sidebar is correct rather than a fallback to one role's menu.
  const navItems =
    identity === null ? [] : identity.role === 'corp' ? CORP_NAV : DMU_NAV

  return (
    <Sidebar variant="inset" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link to="/" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <FileTextIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">DMCU Reports</span>
                <span className="truncate text-xs">Cited briefings</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarMenu>
            {navItems.map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton
                  tooltip={item.title}
                  render={<Link to={item.to} />}
                >
                  <item.icon />
                  <span>{item.title}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
