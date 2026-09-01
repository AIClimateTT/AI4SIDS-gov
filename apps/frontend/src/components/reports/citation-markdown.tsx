import type { MouseEvent } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'

import { cn } from '@/lib/utils'
import { sourceLabel, sourceOf } from '@/components/shared/source-badge'
import type { FactSource } from '@/components/shared/source-badge'
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
  /**
   * cid → the data module that produced that fact, from the report's own fact
   * table. Supplied, each marker is tinted by its source, so a reader can see
   * which half of a sentence rests on a corporation's signed-off figures and
   * which on unverified field observation without opening the appendix.
   *
   * Optional: omitted, markers fall back to the neutral styling, which is what
   * a report rendered without its fact table gets.
   */
  sourceByCid?: Record<string, string>
  className?: string
}

/**
 * Marker styling per source. Kept here rather than in a cva because the marker
 * is a button inside prose and needs its own hover and size treatment; the
 * colour tokens are the same ones SourceBadge uses.
 */
const MARKER_CLASS: Record<FactSource, string> = {
  sitreps:
    'bg-source-sitrep-surface text-source-sitrep hover:bg-source-sitrep/20',
  survey123:
    'bg-source-field-surface text-source-field hover:bg-source-field/20',
  other: 'bg-primary/10 text-primary hover:bg-primary/20',
}

function isCitationHash(href: string | undefined): string | null {
  if (!href) return null
  const match = href.match(/^#citation-(C\d{3})$/)
  return match?.[1] ?? null
}

export function CitationMarkdown({
  markdown,
  violations = [],
  sourceByCid,
  className,
}: CitationMarkdownProps) {
  const prepared = prepareReportMarkdown(markdown, violations)

  return (
    <div
      className={cn(
        // Base size, not prose-sm: this is a document for a Minister, and the
        // fact table has its own column so the briefing never needed to be
        // squeezed. max-w-[68ch] holds the measure near 65 characters — it was
        // running to ~99, which is well past comfortable for continuous prose.
        'prose max-w-[68ch] dark:prose-invert',
        'prose-headings:scroll-mt-20',
        // Section titles need to read as sections. repairReportStructure
        // promotes the model's bold-paragraph titles to h3, so this is what
        // gives them their weight.
        'prose-h3:mt-8 prose-h3:mb-2 prose-h3:text-base prose-h3:font-semibold prose-h3:tracking-tight',
        'prose-p:my-3 prose-li:my-0.5',
        // Figures in a briefing are scanned down the page, not read.
        'prose-td:tabular-nums prose-th:text-xs prose-th:uppercase prose-th:tracking-wide',
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
              const source = sourceOf(sourceByCid?.[cid])
              return (
                <button
                  type="button"
                  data-source={source}
                  // The title carries the source in words. Colour alone must
                  // never be the only encoding, and the marker is too small to
                  // hold a label.
                  title={`${cid} — ${sourceLabel(sourceByCid?.[cid])}`}
                  className={cn(
                    'inline cursor-pointer rounded-sm px-1 font-mono text-[0.85em] font-medium',
                    MARKER_CLASS[source],
                  )}
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
