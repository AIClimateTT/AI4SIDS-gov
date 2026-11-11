import { useState } from 'react'
import { CircleHelpIcon } from 'lucide-react'

import { requestTourRestart } from '@/components/corp/corp-tour-state'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import { SidebarMenuButton } from '@/components/ui/sidebar'

const RULES = [
  'The report is built from the Facts list. The count there is the count that will be sent.',
  'Situation overview, alert wording, and present activity are left off the report when those boxes are empty. Text typed in a box stays as typed.',
  'If the reply says it could not read the update, send it again in a shorter sentence.',
  'Final is the copy that will be sent. Draft may show short codes.',
  'A yellow card must be confirmed before a report that includes incidents can be issued.',
  'After Issue, that conversation cannot be changed. A correction is a new report.',
]

export function CorpTips() {
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<SidebarMenuButton tooltip="Tips" />}>
        <CircleHelpIcon />
        <span>Tips</span>
      </PopoverTrigger>
      <PopoverContent side="right" align="end" className="w-80">
        <PopoverHeader>
          <PopoverTitle>Filing a report</PopoverTitle>
        </PopoverHeader>
        <ul className="list-disc space-y-2 pl-4 text-sm">
          {RULES.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
        <Button
          type="button"
          size="sm"
          className="w-full"
          onClick={() => {
            setOpen(false)
            requestTourRestart()
          }}
        >
          Show me around
        </Button>
      </PopoverContent>
    </Popover>
  )
}
