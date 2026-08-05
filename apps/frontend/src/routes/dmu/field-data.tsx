import { createFileRoute } from '@tanstack/react-router'

import { FormPlaceholder, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'

export const Route = createFileRoute('/dmu/field-data')({ component: IngestPage })

function IngestPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Ingest"
        description="Upload Survey123 CSV exports into the incident store. To file a situation report, go to /corp instead."
      />

      <ContentCard
        title="Upload file"
        description="Choose a module, attach a CSV, and review the ingest result. Form fields land in the next phase."
      >
        <FormPlaceholder
          title="Ingest form placeholder"
          description="Module selector and file upload will use the shared form convention next."
        />
      </ContentCard>
    </div>
  )
}
