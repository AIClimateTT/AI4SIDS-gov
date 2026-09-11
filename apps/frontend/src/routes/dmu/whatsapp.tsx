import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { WhatsAppSourceForm } from '@/components/whatsapp/source-form'
import { WhatsAppDraftWorkspace, sourceTitle } from '@/components/whatsapp/draft-workspace'
import { formatWhen } from '@/lib/format-when'
import { useExtractWhatsApp, whatsappQueries } from '@/lib/queries/whatsapp'

type WhatsAppSearch = { draft?: number }

export const Route = createFileRoute('/dmu/whatsapp')({
  validateSearch: (search: Record<string, unknown>): WhatsAppSearch => {
    const raw = search.draft
    const value =
      typeof raw === 'string' ? Number(raw) : typeof raw === 'number' ? raw : NaN
    return Number.isInteger(value) && value > 0 ? { draft: value } : {}
  },
  component: WhatsAppPage,
})

function toIsoDateTime(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}

function WhatsAppPage() {
  const { draft: draftId } = Route.useSearch()
  const navigate = useNavigate()

  if (draftId) {
    return (
      <WhatsAppDraftWorkspace
        draftId={draftId}
        onNewExtract={() => void navigate({ to: '/dmu/whatsapp', search: {} })}
      />
    )
  }

  return (
    <UploadView
      onOpened={(id) => {
        void navigate({ to: '/dmu/whatsapp', search: { draft: id } })
      }}
    />
  )
}

function UploadView({ onOpened }: { onOpened: (id: number) => void }) {
  const extract = useExtractWhatsApp()
  const draftsQuery = useQuery(whatsappQueries.list())

  return (
    <div className="space-y-6">
      <PageHeader
        title="WhatsApp hour"
        description="Paste a snippet or upload a .txt export, extract a draft, then chat to capture a provisional briefing for the minister."
      />
      <RoleMismatchNotice expected="dmu" />

      {draftsQuery.data && draftsQuery.data.length > 0 ? (
        <ContentCard
          title="Recent drafts"
          description="Resume a working set instead of starting again."
        >
          <ul className="space-y-2">
            {draftsQuery.data.map((item) => (
              <li key={item.id}>
                <Button
                  variant="ghost"
                  className="h-auto w-full justify-start px-2 py-2 text-left"
                  onClick={() => onOpened(item.id)}
                >
                  <span className="flex w-full flex-col">
                    <span className="text-sm font-medium">{sourceTitle(item)}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.incident_count} incidents · {item.log_count} logs ·{' '}
                      {formatWhen(item.updated_at)}
                    </span>
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        </ContentCard>
      ) : null}

      <ContentCard
        title="Start from context"
        description="Paste the hour, or WhatsApp → Chat → Export chat → Without media."
      >
        <WhatsAppSourceForm
          pending={extract.isPending}
          error={extract.error?.message}
          onSubmit={async (input) => {
            const extracted = await extract.mutateAsync({
              file: input.file,
              text: input.text,
              asAt: toIsoDateTime(input.asAt),
            })
            onOpened(extracted.id)
          }}
        />
      </ContentCard>
    </div>
  )
}
