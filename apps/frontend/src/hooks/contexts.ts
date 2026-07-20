import { createFormHookContexts } from '@tanstack/react-form'

// Create contexts for field and form access
export const { fieldContext, useFieldContext, formContext, useFormContext } =
  createFormHookContexts()
