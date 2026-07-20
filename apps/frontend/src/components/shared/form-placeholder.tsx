import { cn } from '@/lib/utils'

type FormPlaceholderProps = {
  title?: string
  description?: string
  className?: string
}

export function FormPlaceholder({
  title = 'Form coming later',
  description = 'This form will be wired with the shared form convention in a later phase.',
  className,
}: FormPlaceholderProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-dashed bg-muted/20 px-6 py-10 text-center',
        className,
      )}
    >
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
