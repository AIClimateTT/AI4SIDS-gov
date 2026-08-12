import { Input } from '@/components/ui/input'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { useFieldContext } from '@/hooks/contexts'
import { FieldErrors } from '@/components/forms/field-error'

type FileFieldProps = {
  label: string
  accept?: string
  helpText?: string
  disabled?: boolean
}

/**
 * A single optional file input. Browsers refuse to let script set a file
 * input's value, so this field is intentionally uncontrolled — it only reads
 * the chosen File out via onChange and never writes one back in.
 */
export function FileField({ label, accept, helpText, disabled }: FileFieldProps) {
  const field = useFieldContext<File | undefined>()

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name}>{label}</FieldLabel>
      <Input
        id={field.name}
        name={field.name}
        type="file"
        accept={accept}
        onChange={(event) => field.handleChange(event.target.files?.[0] ?? undefined)}
        onBlur={field.handleBlur}
        disabled={disabled}
        aria-invalid={
          field.state.meta.isTouched && field.state.meta.errors.length > 0
        }
      />
      {field.state.value ? (
        <FieldDescription>{field.state.value.name}</FieldDescription>
      ) : null}
      {helpText ? <FieldDescription>{helpText}</FieldDescription> : null}
      <FieldErrors meta={field.state.meta} />
    </Field>
  )
}
