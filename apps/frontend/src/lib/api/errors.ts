import axios from 'axios'

/** Map FastAPI / axios errors into a user-facing message. */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : ''
          return loc ? `${loc}: ${item.msg ?? 'invalid'}` : (item.msg ?? 'invalid')
        })
        .join(', ')
    }
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return 'Request failed'
}

export async function withApiError<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn()
  } catch (error) {
    throw new Error(getErrorMessage(error))
  }
}
