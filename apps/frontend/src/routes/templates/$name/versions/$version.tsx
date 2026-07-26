import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { TemplateVersionDetails } from '@/components/templates/template-version-details'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { templateQueries } from '@/lib/queries/templates'

export const Route = createFileRoute('/templates/$name/versions/$version')({
  component: TemplateVersionPage,
})

function TemplateVersionPage() {
  const { name, version } = Route.useParams()
  const versionNumber = Number(version)
  const { data, isPending, isError, error } = useQuery(
    templateQueries.detail(name, versionNumber),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={data?.title ?? `${name} v${version}`}
        description="Read-only snapshot of an immutable template version."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              render={
                <Link to="/templates/$name" params={{ name }} />
              }
            >
              Version history
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

      {isPending ? <LoadingBlock rows={6} /> : null}

      {isError ? (
        <EmptyState
          title="Could not load template version"
          description={error.message}
        />
      ) : null}

      {data ? <TemplateVersionDetails template={data} readOnly /> : null}
    </div>
  )
}
