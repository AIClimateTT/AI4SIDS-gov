import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import {
  ReportPrintDocument,
  reportStatusLine,
} from '@/components/reports/report-print-document'
import { EmptyState, LoadingBlock } from '@/components/shared'
import { reportQueries } from '@/lib/queries/reports'

type PrintSearch = { auto?: boolean }

export const Route = createFileRoute('/dmu/print/$reportId')({
  validateSearch: (search: Record<string, unknown>): PrintSearch => ({
    auto: search.auto === true || search.auto === 'true',
  }),
  component: ReportPrintRoute,
})

function ReportPrintRoute() {
  const { reportId } = Route.useParams()
  const { auto } = Route.useSearch()
  const { data, isError, error } = useQuery(reportQueries.detail(reportId))
  const printed = useRef(false)

  useEffect(() => {
    if (!auto || printed.current || !data?.final_markdown) return
    printed.current = true
    // One frame so the markdown is laid out before the dialog freezes paint.
    const id = requestAnimationFrame(() => window.print())
    return () => cancelAnimationFrame(id)
  }, [auto, data])

  if (isError) {
    return <EmptyState title="Could not load report" description={error.message} />
  }
  if (!data) return <LoadingBlock rows={8} />

  return (
    <ReportPrintDocument
      title={data.period ? `${data.title}, ${data.period}` : data.title}
      statusLine={reportStatusLine(data)}
      markdown={data.final_markdown}
    />
  )
}
