import type { ComponentProps } from 'react'
import { Link, useRouterState } from '@tanstack/react-router'
import type { LinkProps } from '@tanstack/react-router'
import type { LucideIcon } from 'lucide-react'
import {
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  MessageSquareIcon,
  UploadIcon,
  UsersIcon,
} from 'lucide-react'

import { useIdentity } from '@/hooks/use-identity'
import { isAdmin, isDmuWorkspace } from '@/lib/identity'

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

type NavItem = {
  title: string
  to: NonNullable<LinkProps['to']>
  icon: LucideIcon
  /**
   * Only this exact path counts as "here". The dashboard sits at the root of
   * the DMU tree, so a prefix match would light it up on every DMU page —
   * which is exactly what the router's default fuzzy matching does, and why
   * active state is computed here rather than read off the `<Link>`.
   */
  exact?: boolean
}

type NavGroup = {
  label: string
  items: NavItem[]
  /** Pushed to the foot of the sidebar, beneath the day-to-day work. */
  recessed?: boolean
}

/**
 * What an officer does during an event sits on top; setup that changes
 * between events sits beneath it.
 */
const DMU_NAV: NavGroup[] = [
  {
    label: 'Operations',
    items: [
      {
        title: 'Dashboard',
        to: '/dmu',
        icon: LayoutDashboardIcon,
        exact: true,
      },
      { title: 'Reports', to: '/dmu/reports', icon: FileTextIcon },
      { title: 'Field data', to: '/dmu/field-data', icon: UploadIcon },
      { title: 'WhatsApp', to: '/dmu/whatsapp', icon: MessageSquareIcon },
    ],
  },
  {
    label: 'Administration',
    recessed: true,
    items: [
      { title: 'Templates', to: '/dmu/admin/templates', icon: LibraryIcon },
      { title: 'Modules', to: '/dmu/admin/modules', icon: DatabaseIcon },
      { title: 'Users', to: '/dmu/admin/users', icon: UsersIcon },
    ],
  },
]

/**
 * Whether `pathname` is at, or (unless `exact`) somewhere beneath, `to`.
 * Trailing slashes are ignored on both sides, so `/dmu/` is the dashboard.
 */
export function isNavItemActive(
  pathname: string,
  to: string,
  exact = false,
): boolean {
  const path = pathname.replace(/\/+$/, '') || '/'
  const target = to.replace(/\/+$/, '') || '/'
  if (path === target) return true
  return !exact && path.startsWith(`${target}/`)
}

export function AppSidebar(props: ComponentProps<typeof Sidebar>) {
  const { identity } = useIdentity()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const groups = isDmuWorkspace(identity)
    ? isAdmin(identity)
      ? DMU_NAV
      : DMU_NAV.filter((group) => group.label !== 'Administration')
    : []

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
        {groups.map((group) => (
          <SidebarGroup
            key={group.label}
            className={group.recessed ? 'mt-auto' : undefined}
          >
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton
                    tooltip={item.title}
                    isActive={isNavItemActive(pathname, item.to, item.exact)}
                    render={<Link to={item.to} />}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
