import type { ReactNode } from 'react'

import { ContentCard } from '@/components/shared/content-card'

type StatCardProps = {
  label: string
  value: ReactNode
  hint?: string
}

export function StatCard({ label, value, hint }: StatCardProps) {
  return (
    <ContentCard size="sm" title={label} description={hint}>
      <p className="text-3xl font-semibold tracking-tight">{value}</p>
    </ContentCard>
  )
}
