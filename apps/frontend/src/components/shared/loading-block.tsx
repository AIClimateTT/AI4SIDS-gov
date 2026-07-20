import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

type LoadingBlockProps = {
  rows?: number
  className?: string
}

export function LoadingBlock({ rows = 3, className }: LoadingBlockProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  )
}
