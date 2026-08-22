import type { ComponentProps } from 'react'
import { Link } from '@tanstack/react-router'
import {
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  BoxesIcon,
  MessageSquareIcon,
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

const DMU_NAV = [
  { title: 'Dashboard', to: '/dmu', icon: LayoutDashboardIcon },
  { title: 'Field data', to: '/dmu/field-data', icon: UploadIcon },
  { title: 'WhatsApp', to: '/dmu/whatsapp', icon: MessageSquareIcon },
  { title: 'Reports', to: '/dmu/reports', icon: FileTextIcon },
  { title: 'Templates', to: '/dmu/admin/templates', icon: LibraryIcon },
  { title: 'Modules', to: '/dmu/admin/modules', icon: BoxesIcon },
] as const

export function AppSidebar(props: ComponentProps<typeof Sidebar>) {
  const { identity } = useIdentity()
  const navItems = identity?.role === 'dmu' ? DMU_NAV : []

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
