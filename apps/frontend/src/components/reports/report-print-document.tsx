import { CitationMarkdown } from '@/components/reports/citation-markdown'
import type { ReportStatus } from '@/types/dmcu'

export function reportStatusLine({
  verified,
  status,
}: {
  verified: boolean
  status: ReportStatus
}): string {
  const base = verified ? 'Verified' : 'Unverified'
  return status === 'needs_review' ? `${base} · Needs review` : base
}

/** The page the browser prints: the document and a small header, nothing else. */
export function ReportPrintDocument({
  title,
  statusLine,
  markdown,
}: {
  title: string
  statusLine: string
  markdown: string
}) {
  return (
    <article className="mx-auto max-w-[46rem] bg-white px-10 py-10 text-black print:px-0 print:py-0">
      <header className="mb-6 flex items-baseline justify-between border-b border-black/20 pb-3">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-black/60">{statusLine}</span>
      </header>
      <CitationMarkdown
        markdown={markdown}
        className="prose-headings:break-after-avoid prose-table:break-inside-avoid"
      />
    </article>
  )
}
