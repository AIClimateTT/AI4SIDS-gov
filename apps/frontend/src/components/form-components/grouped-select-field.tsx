import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@dth/ui/components/select'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'

export type GroupedSelectOption = {
  groupLabel: string
  options: Array<{ value: string; label: string }>
}

type Props = {
  label?: string
  labelClassName?: string
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  groups: GroupedSelectOption[]
  placeholder?: string
  required?: boolean
  disabled?: boolean
}

export const GroupedSelectField = ({
  label,
  groups,
  placeholder = 'Select an option',
  required,
  disabled,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
}: Props) => {
  const field = useFieldContext<string | null>()

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

  return (
    <Field className="w-full max-w-xs gap-1.5">
      {label && (
        <FieldLabel htmlFor={field.name} className={labelClassName}>
          {label}
          {required && <span className="text-destructive">*</span>}
        </FieldLabel>
      )}
      {helpTextAbove && helpTextEl}
      <Select
        name={field.name}
        value={field.state.value ?? ''}
        onValueChange={(value) => field.handleChange(value)}
        disabled={disabled}
      >
        <SelectTrigger
          id={field.name}
          name={field.name}
          className="w-full"
          onBlur={field.handleBlur}
          aria-invalid={
            field.state.meta.isTouched && field.state.meta.errors.length > 0
          }
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {groups.map((group) => (
            <SelectGroup key={group.groupLabel}>
              <SelectLabel>{group.groupLabel}</SelectLabel>
              {group.options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}
