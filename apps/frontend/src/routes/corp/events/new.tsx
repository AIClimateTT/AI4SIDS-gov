import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Button } from '@/components/ui/button'
import { CorpRoleNotice } from '@/components/identity/corp-role-notice'
import { useAppForm } from '@/hooks/form'
import { useIdentity } from '@/hooks/use-identity'
import { useCreateEvent } from '@/lib/queries/submissions'

export const Route = createFileRoute('/corp/events/new')({
  component: NewEventPage,
})

const HAZARD_TYPES = ['flood', 'landslide', 'wind', 'fire', 'other'] as const

const newEventSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  hazard_type: z.string().min(1, 'Select a hazard type'),
  started_at: z.string().min(1, 'Start date is required'),
})

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function NewEventPage() {
  const { identity } = useIdentity()
  const navigate = useNavigate()

  const createEvent = useCreateEvent((id) => {
    void navigate({ to: '/corp/events/$eventId', params: { eventId: String(id) } })
  })

  const form = useAppForm({
    defaultValues: {
      title: '',
      hazard_type: '',
      started_at: todayIsoDate(),
    },
    validators: {
      onSubmit: newEventSchema,
    },
    onSubmit: async ({ value }) => {
      if (identity?.role !== 'corp') return
      await createEvent.mutateAsync({
        corporation: identity.corporation,
        title: value.title,
        hazard_type: value.hazard_type,
        started_at: value.started_at,
      })
    },
  })

  if (identity?.role !== 'corp') {
    return (
      <CorpRoleNotice description="Switch to a corporation identity to declare an event." />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Declare an event"
        description="A multi-day storm or hazard is one event — filings under it form a running record."
        actions={
          <Button variant="outline" render={<Link to="/corp" />}>
            Back to events
          </Button>
        }
      />

      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.AppForm>
          <ContentCard title="Event details">
            <div className="grid gap-4 sm:grid-cols-2">
              <form.AppField name="title">
                {(field) => <field.TextField label="Title" required />}
              </form.AppField>
              <form.AppField name="hazard_type">
                {(field) => (
                  <field.SelectField
                    label="Hazard type"
                    required
                    options={HAZARD_TYPES.map((value) => ({
                      value,
                      label: value.charAt(0).toUpperCase() + value.slice(1),
                    }))}
                  />
                )}
              </form.AppField>
              <form.AppField name="started_at">
                {(field) => (
                  <field.TextField label="Start date" type="date" required />
                )}
              </form.AppField>
            </div>
          </ContentCard>

          <div className="flex justify-end">
            <form.SubmitButton label="Declare event" />
          </div>
        </form.AppForm>
      </form>
    </div>
  )
}
