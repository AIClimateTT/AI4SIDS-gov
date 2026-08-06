import { Textarea } from '@/components/ui/textarea'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { useFieldContext } from '@/hooks/contexts'
import { FieldErrors } from '@/components/forms/field-error'

type TextareaFieldProps = {
  label: string
  required?: boolean
  placeholder?: string
  helpText?: string
  disabled?: boolean
  rows?: number
}

export function TextareaField({
  label,
  required,
  placeholder,
  helpText,
  disabled,
  rows = 4,
}: TextareaFieldProps) {
  const field = useFieldContext<string>()

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name}>
        {label}
        {required ? <span className="text-destructive">*</span> : null}
      </FieldLabel>
      <Textarea
        id={field.name}
        name={field.name}
        value={field.state.value ?? ''}
        onChange={(event) => field.handleChange(event.target.value)}
        onBlur={field.handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        aria-invalid={
          field.state.meta.isTouched && field.state.meta.errors.length > 0
        }
      />
      {helpText ? <FieldDescription>{helpText}</FieldDescription> : null}
      <FieldErrors meta={field.state.meta} />
    </Field>
  )
}
