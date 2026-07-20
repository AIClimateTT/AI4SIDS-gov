import { Button } from '@dth/ui/components/button'
import { useFormContext } from '../hooks/contexts'

type Props = {
  label?: string
  className?: string
  disabled?: boolean
}

export const ResetButton = ({ label = 'Reset', className, disabled }: Props) => {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(state) => state.isSubmitting}>
      {(isSubmitting) => (
        <Button
          disabled={disabled || isSubmitting}
          type="button"
          variant="outline"
          className={className}
          onClick={() => form.reset()}
        >
          {label}
        </Button>
      )}
    </form.Subscribe>
  )
}
