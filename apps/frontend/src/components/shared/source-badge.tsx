import { cva } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/**
 * The two data sources, and the authority each carries.
 *
 * `sitreps` holds corporations' own human-verified, signed-off figures and is
 * authoritative. `survey123` holds raw field observation whose rows carry a
 * validation status. The backend forbids merging or summing them, and the
 * ministerial template instructs the model to report divergence rather than
 * reconcile it — so the interface must not render them identically either.
 *
 * A module the frontend does not recognise falls back to `other`: a data module
 * added backend-side must degrade to "unstyled but labelled", never to a blank
 * cell that implies no source at all.
 */
export type FactSource = 'sitreps' | 'survey123' | 'other'

const SOURCE_LABELS: Record<FactSource, string> = {
  sitreps: 'SITREP',
  survey123: 'Field',
  other: 'Other',
}

const SOURCE_TITLES: Record<FactSource, string> = {
  sitreps: "Corporation's own verified figures — authoritative",
  survey123: 'Raw field observation — unverified, corroboration only',
  other: 'Source module not recognised by this interface',
}

export function sourceOf(module: string | undefined): FactSource {
  if (module === 'sitreps' || module === 'survey123') return module
  return 'other'
}

export function sourceLabel(module: string | undefined): string {
  return SOURCE_LABELS[sourceOf(module)]
}

const sourceBadge = cva(
  'inline-flex h-5 w-fit shrink-0 items-center rounded-sm border px-1.5 font-mono text-[0.7rem] font-medium whitespace-nowrap',
  {
    variants: {
      source: {
        sitreps:
          'border-source-sitrep/30 bg-source-sitrep-surface text-source-sitrep',
        survey123:
          'border-source-field/30 bg-source-field-surface text-source-field',
        other: 'border-border bg-muted text-muted-foreground',
      },
    },
    defaultVariants: { source: 'other' },
  },
)

/** Border utility for tinting a row or card by the source of its fact. */
export function sourceEdgeClass(module: string | undefined): string {
  const source = sourceOf(module)
  if (source === 'sitreps') return 'border-l-source-sitrep'
  if (source === 'survey123') return 'border-l-source-field'
  return 'border-l-border'
}

type SourceBadgeProps = {
  module: string | undefined
  className?: string
}

export function SourceBadge({ module, className }: SourceBadgeProps) {
  const source = sourceOf(module)
  return (
    <span
      className={cn(sourceBadge({ source }), className)}
      data-source={source}
      title={SOURCE_TITLES[source]}
    >
      {SOURCE_LABELS[source]}
    </span>
  )
}
