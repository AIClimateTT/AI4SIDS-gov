import { Checkbox } from "@dth/ui/components/checkbox"
import { useFieldContext } from "@hooks/contexts"
import { FieldErrors } from "./field-error"
import {
  Field,
  FieldGroup,
  FieldContent,
  FieldLabel,
  FieldDescription,
} from "@dth/ui/components/field"
import { cn } from "@dth/ui/lib/utils"
type Props = {
  label: string
  labelClassName?: string
  description?: string
  disabled?: boolean
}

export const CheckboxField = ({ label, labelClassName, description, disabled }: Props) => {
  const field = useFieldContext<boolean>()

  return (
 
    <FieldGroup className="max-w-sm">
      <Field orientation="horizontal">
        <Checkbox
          id={field.name}
          name={field.name}
          checked={!!field.state.value}
          onCheckedChange={(checked) => field.handleChange(!!checked)}
          onBlur={field.handleBlur}
          disabled={disabled}
        />
        <FieldContent>
          {/* make the text not wrap */}
          <FieldLabel htmlFor={field.name} className={cn("font-normal", labelClassName)}>{label}</FieldLabel>
          {description && <FieldDescription>{description}</FieldDescription>}
        </FieldContent>
      </Field>
      <FieldErrors meta={field.state.meta} />
    </FieldGroup>
  )
}
