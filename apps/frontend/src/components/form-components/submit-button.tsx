import { Loader2 } from 'lucide-react'
import { Button } from '@dth/ui/components/button'
import { useFormContext } from '../hooks/contexts'

type Props = {
  label: string
  className?: string
  disabled?: boolean
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | null
  formId?: string
}

export const SubmitButton = ({ label, className, disabled, variant, formId }: Props) => {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(state) => [state.isSubmitting, state.canSubmit]}>
      {([isSubmitting, canSubmit]) => (
        <Button
          disabled={isSubmitting || !canSubmit || disabled}
          type="submit"
          form={formId}
          className={className}
          variant={variant}
        >
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {label}
        </Button>
      )}
    </form.Subscribe>
  )
}
