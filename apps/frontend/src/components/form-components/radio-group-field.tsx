import { Field, FieldDescription, FieldLabel, FieldLegend, FieldSet } from '@dth/ui/components/field'
import { RadioGroup, RadioGroupItem } from '@dth/ui/components/radio-group'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'
import { cn } from '@dth/ui/lib/utils'

export type RadioOption = {
  value: string
  label: string
}

type Props = {
  label: string
  options: RadioOption[]
  required?: boolean
  helpText?: string
  helpTextClassName?: string
  labelClassName?: string
  orientation?: 'horizontal' | 'vertical'
  disabled?: boolean
  className?: string
  onAfterChange?: (value: string) => void
}

export const RadioGroupField = ({
  label,
  options,
  required,
  helpText,
  helpTextClassName,
  labelClassName,
  disabled,
  className,
  onAfterChange,
}: Props) => {
  const field = useFieldContext<string>()

  return (
    <FieldSet className="w-full max-w-xs">
      <FieldLegend variant="legend" className={cn(labelClassName)}>
        {label}
        {required && <span className="text-destructive ml-2">*</span>}
      </FieldLegend>
      {helpText && (
        <FieldDescription className={helpTextClassName}>
          {helpText}
        </FieldDescription>
      )}
      <RadioGroup
        value={field.state.value ?? ''}
        onValueChange={(val) => {
          field.handleChange(val)
          onAfterChange?.(val)
        }}
        onBlur={field.handleBlur}
        disabled={disabled}
        className={cn(
          'flex flex-col gap-2',
          className,
        )}
      >
        {options.map((option) => (
          <Field key={option.value} orientation="horizontal">
            <RadioGroupItem
              value={option.value}
              id={`${field.name}-${option.value}`}
              className='bg-background'
            />
            <FieldLabel
              htmlFor={`${field.name}-${option.value}`}
              className="font-normal cursor-pointer"
            >
              {option.label}
            </FieldLabel>
          </Field>
        ))}
      </RadioGroup>
      <FieldErrors meta={field.state.meta} />
    </FieldSet>
  )
}
