import { createFormHook } from '@tanstack/react-form'
import {
  SelectField,
  TextAreaField,
  SubmitButton,
  ResetButton,
  GroupedSelectField,
  TextField,
  CheckboxField,
  SwitchField,
  DatePickerField,
  ComboboxField,
  MultiComboboxField,
  RadioGroupField,
  PasswordTextField,
  PhoneTextField,
} from '@components/forms-components'
import { fieldContext, formContext, useFieldContext, useFormContext } from './contexts'

export { useFieldContext, useFormContext }


// Create the form hook with all field and form components
export const { useAppForm, withFieldGroup, withForm } = createFormHook({
  fieldComponents: {
    TextField,
    PasswordTextField,
    PhoneTextField,
    SelectField,
    TextAreaField,
    GroupedSelectField,
    CheckboxField,
    SwitchField,
    DatePickerField,
    ComboboxField,
    MultiComboboxField,
    RadioGroupField,
  },
  formComponents: {
    SubmitButton,
    ResetButton,
  },
  fieldContext,
  formContext,
})

/**
 * Helper to create a field map for withFieldGroup
 * Use when fields should remain at top-level of the form structure
 */
export function createFieldMap<T extends Record<string, any>>(map: {
  [K in keyof T]: K
}): { [K in keyof T]: K } {
  return map
}

// Re-export types for convenience
export type { AnyFieldMeta } from '@tanstack/react-form'
