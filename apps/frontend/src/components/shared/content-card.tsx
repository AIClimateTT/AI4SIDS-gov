import type { ReactNode } from 'react'

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

type ContentCardProps = {
  title?: ReactNode
  description?: ReactNode
  action?: ReactNode
  footer?: ReactNode
  children?: ReactNode
  size?: 'default' | 'sm'
  className?: string
  contentClassName?: string
}

export function ContentCard({
  title,
  description,
  action,
  footer,
  children,
  size = 'default',
  className,
  contentClassName,
}: ContentCardProps) {
  const hasHeader = title != null || description != null || action != null

  return (
    <Card size={size} className={className}>
      {hasHeader ? (
        <CardHeader>
          {title != null ? <CardTitle>{title}</CardTitle> : null}
          {description != null ? (
            <CardDescription>{description}</CardDescription>
          ) : null}
          {action != null ? <CardAction>{action}</CardAction> : null}
        </CardHeader>
      ) : null}
      {children != null ? (
        <CardContent className={cn(contentClassName)}>{children}</CardContent>
      ) : null}
      {footer != null ? <CardFooter>{footer}</CardFooter> : null}
    </Card>
  )
}
