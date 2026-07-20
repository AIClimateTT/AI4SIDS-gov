import { Switch } from '@dth/ui/components/switch'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'

type Props = {
  label: string
  disabled?: boolean
  labelClassName?: string
  helpText?: string
  helpTextClassName?: string
}

export const SwitchField = ({ label, disabled, helpText, helpTextClassName, labelClassName }: Props) => {
  const field = useFieldContext<boolean>()

  return (
    <Field className="w-full">
      <div className="flex items-center justify-between rounded-lg border p-4">
        <div className="space-y-0.5">
          <FieldLabel htmlFor={field.name} className={labelClassName}>
            {label}
          </FieldLabel>
          {helpText && (
            <FieldDescription className={helpTextClassName}>{helpText}</FieldDescription>
          )}
        </div>
        <Switch
          id={field.name}
          name={field.name}
          checked={!!field.state.value}
          onCheckedChange={(checked) => field.handleChange(checked)}
          onBlur={field.handleBlur}
          disabled={disabled}
        />
      </div>
      <FieldErrors meta={field.state.meta} />
    </Field>
  )
}
