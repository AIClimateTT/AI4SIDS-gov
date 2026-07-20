import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Badge } from '@/components/ui/badge'
import { templateQueries } from '@/lib/queries/templates'

export const Route = createFileRoute('/templates')({
  component: TemplatesPage,
})

function TemplatesPage() {
  const { data, isPending, isError, error } = useQuery(templateQueries.list())

  return (
    <div className="space-y-6">
      <PageHeader
        title="Templates"
        description="Versioned briefing definitions available for report generation."
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load templates"
          description={error.message}
        />
      ) : null}

      {data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((template) => (
            <ContentCard
              key={template.name}
              title={template.title}
              description={template.description}
              action={<Badge variant="outline">v{template.version}</Badge>}
              footer={
                <div className="flex w-full items-center justify-between gap-3">
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {template.name}
                  </p>
                  <Button size="sm" render={<Link to="/reports/new" />}>
                    Generate with this
                  </Button>
                </div>
              }
            >
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Params
                </p>
                <ul className="space-y-1 text-sm">
                  {template.params.map((param) => (
                    <li key={param.name} className="flex items-center gap-2">
                      <span className="font-mono">{param.name}</span>
                      <Badge variant={param.required ? 'secondary' : 'outline'}>
                        {param.required ? 'required' : 'optional'}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            </ContentCard>
          ))}
        </div>
      ) : null}
    </div>
  )
}
