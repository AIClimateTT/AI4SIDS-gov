import { createFileRoute } from '@tanstack/react-router'

import { RecordsView } from '@/components/dmu/records-view'
import type { RecordsSearch } from '@/components/dmu/records-view'
import { PageHeader } from '@/components/shared'

export const Route = createFileRoute('/dmu/records')({
  component: RecordsPage,
  validateSearch: (search: Record<string, unknown>): RecordsSearch => ({
    tab: search.tab === 'logs' ? 'logs' : undefined,
    corporation:
      typeof search.corporation === 'string' ? search.corporation : undefined,
    submission_id:
      typeof search.submission_id === 'number' ? search.submission_id : undefined,
  }),
})

function RecordsPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Incidents & logs"
        description="Everything corporations have filed, all together or for one filed report."
      />
      <RecordsView
        search={search}
        onSearchChange={(next) => void navigate({ search: next, replace: true })}
      />
    </div>
  )
}
