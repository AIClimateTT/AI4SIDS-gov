import { Link, createFileRoute } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { FormPlaceholder, PageHeader } from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'

export const Route = createFileRoute('/reports/new')({
  component: NewReportPage,
})

function NewReportPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate report"
        description="Pick a template and params, then run the citation-checked briefing engine."
        actions={
          <Button variant="outline" render={<Link to="/reports" />}>
            Back to reports
          </Button>
        }
      />

      <ContentCard
        title="Report parameters"
        description="Template selection and param fields will use the shared form convention next."
      >
        <FormPlaceholder
          title="Generate form placeholder"
          description="No form fields yet — wiring comes in the forms phase."
        />
      </ContentCard>
    </div>
  )
}
