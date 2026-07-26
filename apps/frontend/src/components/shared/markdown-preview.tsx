import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

type MarkdownPreviewProps = {
  markdown: string
  className?: string
}

/** Generic markdown renderer. For report citations, use CitationMarkdown. */
export function MarkdownPreview({ markdown, className }: MarkdownPreviewProps) {
  return (
    <div
      className={cn(
        'prose prose-sm max-w-none dark:prose-invert',
        className,
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]}>{markdown}</Markdown>
    </div>
  )
}
