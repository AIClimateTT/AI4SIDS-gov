import { Textarea } from '@dth/ui/components/textarea'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { type JSX } from 'react'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'

type Props = {
  label: string | JSX.Element
  required?: boolean
  placeholder?: string
  autoComplete?: string
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  labelClassName?: string
  disabled?: boolean
  rows?: number
}

export const TextAreaField = ({
  label,
  required,
  placeholder,
  autoComplete,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
  disabled,
  rows = 3,
}: Props) => {
  const field = useFieldContext<string | null>()

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>{helpText}</FieldDescription>
  ) : null

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </FieldLabel>
      {helpTextAbove && helpTextEl}
      <Textarea
        name={field.name}
        id={field.name}
        value={field.state.value ?? ''}
        onChange={(e) => field.handleChange(e.target.value)}
        onBlur={field.handleBlur}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        rows={rows}
        aria-invalid={
          field.state.meta.isTouched && field.state.meta.errors.length > 0
        }
        className="bg-background"
      />
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}
