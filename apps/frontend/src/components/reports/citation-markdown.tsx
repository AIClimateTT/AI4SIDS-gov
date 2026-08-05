import type { MouseEvent } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'

import { cn } from '@/lib/utils'
import type { CitationViolation } from '@/types/dmcu'
import {
  prepareReportMarkdown,
  scrollToCitation,
} from '@/components/reports/citation-utils'

/**
 * rehype-raw parses the raw HTML in the report markdown, which is model-authored
 * prose plus the <mark> spans markViolationSentences injects. Parsing it without
 * sanitising means anything the model emits — a <script>, an onerror handler, a
 * javascript: href — renders as live HTML in the DMU's browser.
 *
 * The default schema drops all of that. It also drops <mark> and every
 * className, which is exactly how violation highlighting is rendered, so
 * <mark> and a class on <mark> alone are allowed back.
 */
const reportSanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), 'mark'],
  attributes: {
    ...defaultSchema.attributes,
    mark: [...(defaultSchema.attributes?.mark ?? []), 'className'],
  },
}

type CitationMarkdownProps = {
  markdown: string
  violations?: CitationViolation[]
  className?: string
}

function isCitationHash(href: string | undefined): string | null {
  if (!href) return null
  const match = href.match(/^#citation-(C\d{3})$/)
  return match?.[1] ?? null
}

export function CitationMarkdown({
  markdown,
  violations = [],
  className,
}: CitationMarkdownProps) {
  const prepared = prepareReportMarkdown(markdown, violations)

  return (
    <div
      className={cn(
        'prose prose-sm max-w-none dark:prose-invert',
        'prose-headings:scroll-mt-20',
        'prose-a:font-medium prose-a:text-primary prose-a:no-underline hover:prose-a:underline',
        '[&_mark.violation-mark]:rounded-sm [&_mark.violation-mark]:bg-destructive/20 [&_mark.violation-mark]:px-0.5 [&_mark.violation-mark]:text-foreground',
        className,
      )}
    >
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, reportSanitizeSchema]]}
        components={{
          a: ({ href, children, ...props }) => {
            const cid = isCitationHash(href)
            if (cid) {
              return (
                <button
                  type="button"
                  className="inline cursor-pointer rounded-sm bg-primary/10 px-1 font-mono text-[0.85em] font-medium text-primary hover:bg-primary/20"
                  onClick={(event: MouseEvent<HTMLButtonElement>) => {
                    event.preventDefault()
                    scrollToCitation(cid)
                  }}
                >
                  {children}
                </button>
              )
            }

            return (
              <a href={href} {...props}>
                {children}
              </a>
            )
          },
        }}
      >
        {prepared}
      </Markdown>
    </div>
  )
}
