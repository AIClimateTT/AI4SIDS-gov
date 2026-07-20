import { cn } from '@/lib/utils'

type MarkdownPreviewProps = {
  markdown: string
  className?: string
}

/** Plain markdown display for scaffolding — swap for a real renderer later. */
export function MarkdownPreview({ markdown, className }: MarkdownPreviewProps) {
  return (
    <pre
      className={cn(
        'overflow-x-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-4 font-mono text-sm leading-relaxed',
        className,
      )}
    >
      {markdown}
    </pre>
  )
}
