import type { UseMutationOptions } from '@tanstack/react-query'

/**
 * Helper for mutation options with correct type inference.
 * Similar to TanStack Query's queryOptions but for mutations.
 */
export function mutationOptions<
  TData = unknown,
  TError = Error,
  TVariables = void,
  TContext = unknown,
>(
  options: UseMutationOptions<TData, TError, TVariables, TContext>,
): UseMutationOptions<TData, TError, TVariables, TContext> {
  return options
}
