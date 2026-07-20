import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { moduleQueries } from '@/lib/queries/modules'

export const Route = createFileRoute('/modules')({ component: ModulesPage })

function ModulesPage() {
  const { data, isPending, isError, error } = useQuery(moduleQueries.list())

  return (
    <div className="space-y-6">
      <PageHeader
        title="Modules"
        description="Registered data modules and the metrics templates can request."
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load modules"
          description={error.message}
        />
      ) : null}

      {data ? (
        <div className="space-y-4">
          {data.map((module) => (
            <ContentCard
              key={module.name}
              title={module.name}
              description={`${module.metrics.length} metrics`}
              action={<Badge variant="outline">{module.name}</Badge>}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Params</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {module.metrics.map((metric) => (
                    <TableRow key={metric.name}>
                      <TableCell className="font-mono text-sm">
                        {metric.name}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {metric.description}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {Object.keys(
                          metric.params_schema?.properties ?? {},
                        ).join(', ') || '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ContentCard>
          ))}
        </div>
      ) : null}
    </div>
  )
}
