import { useQuery } from '@tanstack/react-query'
import { Link, useRouterState } from '@tanstack/react-router'
import { BuildingIcon, ChevronRightIcon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { submissionQueries } from '@/lib/queries/submissions'
import { cn } from '@/lib/utils'
import { deriveWhoReported } from '@/lib/who-reported'

const CORPORATION_PATH = '/dmu/corporations/'

const DOT_CLASSES: Record<string, string> = {
  green: 'bg-alert-green',
  yellow: 'bg-alert-yellow',
  orange: 'bg-alert-orange',
  red: 'bg-alert-red',
  discontinued: 'bg-alert-discontinued',
}

/** All fourteen corporations, each with a dot for its latest alert level. */
export function CorporationsNav() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const onCorporationPage = pathname.startsWith(CORPORATION_PATH)
  const [open, setOpen] = useState(onCorporationPage)
  const filings = useQuery(submissionQueries.list({}))

  useEffect(() => {
    if (onCorporationPage) setOpen(true)
  }, [onCorporationPage])

  const latest = useMemo(() => {
    const { rows } = deriveWhoReported(filings.data ?? [], new Date(), 24)
    return new Map(rows.map((row) => [row.corporation as string, row.latest]))
  }, [filings.data])

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Corporations</SidebarGroupLabel>
      <SidebarMenu>
        <Collapsible open={open} onOpenChange={setOpen} className="group/corporations">
          <SidebarMenuItem>
            <CollapsibleTrigger render={<SidebarMenuButton tooltip="Corporations" />}>
              <BuildingIcon />
              <span>All corporations</span>
              <ChevronRightIcon
                className={cn('ml-auto transition-transform', open && 'rotate-90')}
              />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <SidebarMenuSub>
                {CORPORATION_OPTIONS.map((option) => {
                  const level = latest.get(option.value)?.alert_level
                  return (
                    <SidebarMenuSubItem key={option.value}>
                      <SidebarMenuSubButton
                        isActive={pathname === `${CORPORATION_PATH}${option.value}`}
                        render={
                          <Link
                            to="/dmu/corporations/$corporation"
                            params={{ corporation: option.value }}
                          />
                        }
                      >
                        <span
                          aria-hidden
                          data-level={level ?? 'none'}
                          className={cn(
                            'size-2 shrink-0 rounded-full',
                            (level && DOT_CLASSES[level]) || 'bg-muted-foreground/40',
                          )}
                        />
                        <span className="truncate">{option.label}</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  )
                })}
              </SidebarMenuSub>
            </CollapsibleContent>
          </SidebarMenuItem>
        </Collapsible>
      </SidebarMenu>
    </SidebarGroup>
  )
}
