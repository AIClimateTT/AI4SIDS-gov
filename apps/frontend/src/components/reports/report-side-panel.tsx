import { XIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

/**
 * Sits beside the report rather than over it, because what a panel says is read
 * against the document: Review highlights sentences, Sources explains markers.
 */
export function ReportSidePanel({
  title,
  description,
  onClose,
  children,
}: {
  title: string
  description: string
  onClose: () => void
  children: ReactNode
}) {
  return (
    <aside
      aria-label={title}
      className="order-first max-h-[50vh] overflow-y-auto rounded-xl border bg-card xl:sticky xl:top-4 xl:order-none xl:max-h-[calc(100vh-8rem)]"
    >
      <div className="flex items-start justify-between gap-2 p-4">
        <div className="space-y-1">
          <h2 className="font-medium">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Close ${title}`}
          onClick={onClose}
        >
          <XIcon />
        </Button>
      </div>
      <div className="space-y-6 px-4 pb-4">{children}</div>
    </aside>
  )
}
