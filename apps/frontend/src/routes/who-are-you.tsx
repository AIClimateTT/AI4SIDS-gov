import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { ContentCard } from '@/components/shared/content-card'
import { PageHeader } from '@/components/shared'
import { useIdentity } from '@/hooks/use-identity'
import { CORPORATION_OPTIONS } from '@/lib/corporations'
import { identityHomePath } from '@/lib/identity'
import type { Identity } from '@/lib/identity'

export const Route = createFileRoute('/who-are-you')({
  component: WhoAreYouPage,
})

function WhoAreYouPage() {
  const { setIdentity } = useIdentity()
  const navigate = useNavigate()

  const choose = (identity: Identity) => {
    setIdentity(identity)
    void navigate({ to: identityHomePath(identity) })
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader
        title="Who are you?"
        description="Choose where you work. You can change this at any time from the header."
      />

      <ContentCard
        title="Disaster Management Coordinating Unit"
        description="Review what corporations have reported and produce the ministerial situation report."
      >
        <Button onClick={() => choose({ role: 'dmu' })}>Continue as the DMU</Button>
      </ContentCard>

      <ContentCard
        title="Regional corporation"
        description="File your situation reports and manage your events."
      >
        <div className="grid gap-2 sm:grid-cols-2">
          {CORPORATION_OPTIONS.map((option) => (
            <Button
              key={option.value}
              variant="outline"
              className="justify-start"
              onClick={() => choose({ role: 'corp', corporation: option.value })}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </ContentCard>
    </div>
  )
}
