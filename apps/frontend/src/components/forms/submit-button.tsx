import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useFormContext } from '@/hooks/contexts'

type SubmitButtonProps = {
  label: string
  className?: string
  disabled?: boolean
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost'
}

export function SubmitButton({
  label,
  className,
  disabled,
  variant = 'default',
}: SubmitButtonProps) {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(state) => [state.isSubmitting, state.canSubmit]}>
      {([isSubmitting, canSubmit]) => (
        <Button
          type="submit"
          disabled={isSubmitting || !canSubmit || disabled}
          className={className}
          variant={variant}
        >
          {isSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
          {label}
        </Button>
      )}
    </form.Subscribe>
  )
}
