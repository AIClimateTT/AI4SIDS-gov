import type { AnyFieldMeta } from '@tanstack/react-form'
import type { ZodError } from 'zod'

type FieldErrorProps = {
  meta: AnyFieldMeta
}

export function formatFieldError(error: unknown): string {
  if (typeof error === 'string') return error
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message: unknown }).message)
  }
  return 'Please check this field'
}

export const FieldErrors = ({ meta }: FieldErrorProps) => {
  if (!meta.isTouched || !meta.errors?.length) return null

  return (
    <div className="space-y-1">
      {meta.errors.map((error: ZodError | string, index: number) => (
        <p key={index} className="text-xs font-medium text-destructive">
          {formatFieldError(error)}
        </p>
      ))}
    </div>
  )
}
