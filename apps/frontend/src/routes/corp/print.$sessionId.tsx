import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { ReportPrintDocument } from '@/components/reports/report-print-document'
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
    <ReportPrintDocument
      title={corporation}
      statusLine={
        issued && session.report_id ? `Report ${session.report_id}` : 'Draft — not issued'
      }
      markdown={stripCitationMarkup(sitrep.final_markdown)}
    />
  )
}
