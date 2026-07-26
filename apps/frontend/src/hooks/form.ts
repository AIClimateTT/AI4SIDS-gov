import { createFormHook } from '@tanstack/react-form'

import {
  SelectField,
  SubmitButton,
  TextField,
} from '@/components/forms'
import { fieldContext, formContext, useFieldContext, useFormContext } from './contexts'

export { useFieldContext, useFormContext }

export const { useAppForm, withFieldGroup, withForm } = createFormHook({
  fieldComponents: {
    TextField,
    SelectField,
  },
  formComponents: {
    SubmitButton,
  },
  fieldContext,
  formContext,
})

export function createFieldMap<T extends Record<string, unknown>>(map: {
  [K in keyof T]: K
}): { [K in keyof T]: K } {
  return map
}

export type { AnyFieldMeta } from '@tanstack/react-form'
