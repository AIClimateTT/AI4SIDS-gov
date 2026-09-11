import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { CitationMarkdown } from '@/components/reports/citation-markdown'
import { stripCitationMarkup } from '@/components/reports/citation-utils'
import { EmptyState, LoadingBlock } from '@/components/shared'
import { formatDisplayValue } from '@/lib/format-display'
import { captureQueries } from '@/lib/queries/capture'

type PrintSearch = {
  /** Set when opened from the pane's Download PDF button so the browser's
   * print dialog comes up on its own; a hand-typed URL just shows the page. */
  auto?: boolean
}

export const Route = createFileRoute('/corp/print/$sessionId')({
  validateSearch: (search: Record<string, unknown>): PrintSearch => ({
    auto: search.auto === true || search.auto === 'true',
  }),
  component: SitrepPrintRoute,
})

function SitrepPrintRoute() {
  const { sessionId } = Route.useParams()
  const { auto } = Route.useSearch()
  const sessionQuery = useQuery(captureQueries.detail(Number(sessionId)))
  const printed = useRef(false)
  const session = sessionQuery.data
  const sitrep = session?.sitrep

  useEffect(() => {
    if (!auto || printed.current || !sitrep) return
    printed.current = true
    // One frame so the markdown is laid out before the dialog freezes paint.
    const id = requestAnimationFrame(() => window.print())
    return () => cancelAnimationFrame(id)
  }, [auto, sitrep])

  if (sessionQuery.isError) {
    return (
      <EmptyState
        title="Could not load sitrep"
        description={sessionQuery.error.message}
      />
    )
  }

  if (!session) {
    return <LoadingBlock rows={8} />
  }

  if (!sitrep) {
    return (
      <EmptyState
        title="No sitrep to print"
        description="Generate a draft for this conversation first."
      />
    )
  }

  const corporation = formatDisplayValue(session.corporation)
  const issued = session.status === 'filed'

  return (
    <article className="mx-auto max-w-[46rem] bg-white px-10 py-10 text-black print:px-0 print:py-0">
      <header className="mb-6 flex items-baseline justify-between border-b border-black/20 pb-3">
        <span className="text-sm font-semibold">{corporation}</span>
        <span className="text-xs text-black/60">
          {issued && session.report_id
            ? `Report ${session.report_id}`
            : 'Draft — not issued'}
        </span>
      </header>
      <CitationMarkdown
        markdown={stripCitationMarkup(sitrep.final_markdown)}
        className="prose-headings:break-after-avoid prose-table:break-inside-avoid"
      />
    </article>
  )
}
