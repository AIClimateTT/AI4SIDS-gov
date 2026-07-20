import { createFileRoute } from '@tanstack/react-router'

import { FormPlaceholder, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'

export const Route = createFileRoute('/ingest')({ component: IngestPage })

function IngestPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Ingest"
        description="Upload Survey123 or SITREP CSV exports into the incident store."
      />

      <ContentCard
        title="Upload file"
        description="Choose a module, attach a CSV, and review the ingest result. Form fields land in the next phase."
      >
        <FormPlaceholder
          title="Ingest form placeholder"
          description="Module selector, corporation (for sitreps), and file upload will use the shared form convention next."
        />
      </ContentCard>
    </div>
  )
}
