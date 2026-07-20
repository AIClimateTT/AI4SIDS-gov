import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@dth/ui/components/select'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'

type Props<TType extends 'string' | 'number' = 'string'> = {
  label?: string
  options: Array<{
    value: TType extends 'string' ? string : number
    label: string
  }>
  type: TType
  required?: boolean
  placeholder?: string
  disabled?: boolean
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  labelClassName?: string
}

export const SelectField = <TType extends 'string' | 'number' = 'string'>({
  label,
  options,
  required,
  type,
  placeholder = 'Select an option',
  disabled,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
}: Props<TType>) => {
  const field = useFieldContext<string | number | null>()

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

  return (
    <Field className="w-full gap-1.5">
      {label && (
        <FieldLabel htmlFor={field.name} className={labelClassName}>
          {label}
          {required && <span className="text-destructive">*</span>}
        </FieldLabel>
      )}
      {helpTextAbove && helpTextEl}
      <Select
        name={field.name}
        value={field.state.value?.toString() ?? ''}
        onValueChange={(value) => {
          field.handleChange(type === 'number' ? Number(value) : value)
        }}
        disabled={disabled}
      >
        <SelectTrigger
          id={field.name}
          name={field.name}
          className="w-full bg-background"
          onBlur={field.handleBlur}
          aria-invalid={
            field.state.meta.isTouched && field.state.meta.errors.length > 0
          }
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={`${option.value}`}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}
