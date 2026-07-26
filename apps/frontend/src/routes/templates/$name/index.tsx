import { Link, createFileRoute } from '@tanstack/react-router'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { templateQueries } from '@/lib/queries/templates'
import { Button } from '@/components/ui/button'
import { useQuery } from '@tanstack/react-query'

export const Route = createFileRoute('/templates/$name/')({
  component: TemplateHistoryPage,
})

function TemplateHistoryPage() {
  const { name } = Route.useParams()
  const { data, isPending, isError, error } = useQuery(
    templateQueries.versions(name),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={name}
        description="Immutable template versions. Edit by creating a new version."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" render={<Link to="/templates" />}>
              All templates
            </Button>
            <Button
              render={
                <Link to="/templates/$name/new" params={{ name }} />
              }
            >
              Create new version
            </Button>
          </div>
        }
      />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load versions"
          description={error.message}
        />
      ) : null}

      {data ? (
        <div className="space-y-3">
          {data.map((version) => (
            <Link
              key={version.version}
              to="/templates/$name/versions/$version"
              params={{ name, version: String(version.version) }}
              className="block rounded-lg border bg-card px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{version.title}</p>
                  <p className="text-sm text-muted-foreground">
                    v{version.version} ·{' '}
                    {new Date(version.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="text-sm text-muted-foreground">View</span>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  )
}
