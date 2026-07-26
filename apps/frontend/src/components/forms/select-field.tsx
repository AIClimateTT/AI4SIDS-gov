import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { useFieldContext } from '@/hooks/contexts'
import { FieldErrors } from '@/components/forms/field-error'

type SelectFieldProps = {
  label: string
  options: Array<{ value: string; label: string }>
  required?: boolean
  placeholder?: string
  helpText?: string
  disabled?: boolean
}

export function SelectField({
  label,
  options,
  required,
  placeholder = 'Select an option',
  helpText,
  disabled,
}: SelectFieldProps) {
  const field = useFieldContext<string>()

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name}>
        {label}
        {required ? <span className="text-destructive">*</span> : null}
      </FieldLabel>
      <Select
        value={field.state.value ?? ''}
        onValueChange={(value) => {
          if (value) field.handleChange(value)
        }}
        disabled={disabled}
      >
        <SelectTrigger
          id={field.name}
          className="w-full"
          onBlur={field.handleBlur}
          aria-invalid={
            field.state.meta.isTouched && field.state.meta.errors.length > 0
          }
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {helpText ? <FieldDescription>{helpText}</FieldDescription> : null}
      <FieldErrors meta={field.state.meta} />
    </Field>
  )
}
