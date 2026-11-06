import { createFileRoute, notFound } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { FilingsByEvent } from '@/components/dmu/filings-by-event'
import { RecordsView } from '@/components/dmu/records-view'
import { AlertLevelBadge, EmptyState, LoadingBlock, PageHeader } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { CORPORATION_LABELS, isCanonicalCorporation } from '@/lib/corporations'
import { formatWhen } from '@/lib/format-when'
import { eventQueries, submissionQueries } from '@/lib/queries/submissions'

type CorporationTab = 'filings' | 'incidents' | 'logs'

type CorporationSearch = {
  tab?: CorporationTab
  submission_id?: number
}

const TABS: { value: CorporationTab; label: string }[] = [
  { value: 'filings', label: 'Filings' },
  { value: 'incidents', label: 'Incidents' },
  { value: 'logs', label: 'Situation logs' },
]

export const Route = createFileRoute('/dmu/corporations/$corporation')({
  component: CorporationPage,
  validateSearch: (search: Record<string, unknown>): CorporationSearch => ({
    tab: search.tab === 'incidents' || search.tab === 'logs' ? search.tab : undefined,
    submission_id:
      typeof search.submission_id === 'number' ? search.submission_id : undefined,
  }),
  // A slug outside the fourteen is a 404, not an empty page. An unknown
  // corporation matches no rows, and a page of zeroes for a region that may
  // have filed plenty reads as an authoritative "nothing happened" — the same
  // failure POST /reports guards against server-side.
  beforeLoad: ({ params }) => {
    if (!isCanonicalCorporation(params.corporation)) throw notFound()
  },
})

function CorporationPage() {
  const { corporation } = Route.useParams()
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const tab = search.tab ?? 'filings'

  const label = isCanonicalCorporation(corporation)
    ? CORPORATION_LABELS[corporation]
    : corporation

  const filings = useQuery(submissionQueries.list({ corporation }))
  const events = useQuery(eventQueries.list(corporation))

  const latest = useMemo(
    () =>
      [...(filings.data ?? [])].sort(
        (a, b) => new Date(b.as_at).getTime() - new Date(a.as_at).getTime(),
      )[0],
    [filings.data],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={label}
        description={latest ? `Last filed ${formatWhen(latest.as_at)}` : 'Never filed'}
        actions={latest ? <AlertLevelBadge level={latest.alert_level} /> : null}
      />

      <div className="flex gap-2">
        {TABS.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={tab === option.value ? 'default' : 'outline'}
            onClick={() =>
              void navigate({
                search: {
                  tab: option.value === 'filings' ? undefined : option.value,
                  submission_id: search.submission_id,
                },
                replace: true,
              })
            }
          >
            {option.label}
          </Button>
        ))}
      </div>

      {tab === 'filings' ? (
        <>
          {filings.isPending || events.isPending ? <LoadingBlock rows={4} /> : null}
          {filings.isError ? (
            <EmptyState title="Could not load filings" description={filings.error.message} />
          ) : null}
          {filings.data && events.data ? (
            <FilingsByEvent
              corporation={corporation}
              filings={filings.data}
              events={events.data}
            />
          ) : null}
        </>
      ) : (
        <RecordsView
          lockedCorporation={corporation}
          search={{ tab, submission_id: search.submission_id }}
          onSearchChange={(next) =>
            void navigate({
              search: { tab, submission_id: next.submission_id },
              replace: true,
            })
          }
        />
      )}
    </div>
  )
}
