import type { ReactNode } from 'react'
import { cn } from '@dth/ui/lib/utils'

type Props = {
  title: string
  description?: string
  children: ReactNode
  className?: string
}

export const FormSection = ({ title, description, children, className }: Props) => {
  return (
    <section className={cn('space-y-6', className)}>
      <div className="space-y-1">
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  )
}
