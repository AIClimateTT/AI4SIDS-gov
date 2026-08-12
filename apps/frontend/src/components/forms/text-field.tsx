import { Input } from '@/components/ui/input'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { useFieldContext } from '@/hooks/contexts'
import { FieldErrors } from '@/components/forms/field-error'

type TextFieldProps = {
  label: string
  type?: 'text' | 'email' | 'date' | 'datetime-local'
  required?: boolean
  placeholder?: string
  helpText?: string
  disabled?: boolean
}

export function TextField({
  label,
  type = 'text',
  required,
  placeholder,
  helpText,
  disabled,
}: TextFieldProps) {
  const field = useFieldContext<string>()

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name}>
        {label}
        {required ? <span className="text-destructive">*</span> : null}
      </FieldLabel>
      <Input
        id={field.name}
        name={field.name}
        type={type}
        value={field.state.value ?? ''}
        onChange={(event) => field.handleChange(event.target.value)}
        onBlur={field.handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={
          field.state.meta.isTouched && field.state.meta.errors.length > 0
        }
      />
      {helpText ? <FieldDescription>{helpText}</FieldDescription> : null}
      <FieldErrors meta={field.state.meta} />
    </Field>
  )
}
