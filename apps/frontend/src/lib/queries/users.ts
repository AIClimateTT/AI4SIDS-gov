import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  activateUser,
  createUser,
  deactivateUser,
  deleteUser,
  getUsers,
  setUserPassword,
  updateUser,
} from '@/lib/api/users'
import { mutationOptions } from '@/lib/queries/tanstack-helpers'
import type { UserWriteInput } from '@/types/users'

// ---------------------------------------------------------------------------
// Key Factory
// ---------------------------------------------------------------------------

export const userKeys = {
  all: () => ['users'] as const,
  lists: () => [...userKeys.all(), 'list'] as const,
  list: () => [...userKeys.lists()] as const,
}

// ---------------------------------------------------------------------------
// Query Options
// ---------------------------------------------------------------------------

export const userQueries = {
  list: () =>
    queryOptions({
      queryKey: userKeys.list(),
      queryFn: getUsers,
    }),
}

// ---------------------------------------------------------------------------
// Mutation Options
// ---------------------------------------------------------------------------

export const userMutations = {
  create: () =>
    mutationOptions({
      mutationFn: createUser,
    }),
  update: () =>
    mutationOptions({
      mutationFn: ({
        userId,
        data,
      }: {
        userId: string
        data: UserWriteInput
      }) => updateUser(userId, data),
    }),
  activate: () =>
    mutationOptions({
      mutationFn: activateUser,
    }),
  deactivate: () =>
    mutationOptions({
      mutationFn: deactivateUser,
    }),
  delete: () =>
    mutationOptions({
      mutationFn: deleteUser,
    }),
  setPassword: () =>
    mutationOptions({
      mutationFn: ({
        userId,
        password,
      }: {
        userId: string
        password: string
      }) => setUserPassword(userId, password),
    }),
}

// ---------------------------------------------------------------------------
// Hook Wrappers
// ---------------------------------------------------------------------------

export function useUsers() {
  return useQuery(userQueries.list())
}

function invalidateUsers(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: userKeys.list() })
}

export function useCreateUser(onSuccess?: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.create(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('User created')
      onSuccess?.()
    },
    onError: (error: Error) =>
      toast.error('Failed to create user', { description: error.message }),
  })
}

export function useUpdateUser(onSuccess?: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.update(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('User updated')
      onSuccess?.()
    },
    onError: (error: Error) =>
      toast.error('Failed to update user', { description: error.message }),
  })
}

export function useActivateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.activate(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('User activated')
    },
    onError: (error: Error) =>
      toast.error('Failed to activate user', { description: error.message }),
  })
}

export function useDeactivateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.deactivate(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('User deactivated')
    },
    onError: (error: Error) =>
      toast.error('Failed to deactivate user', { description: error.message }),
  })
}

export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.delete(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('User deleted')
    },
    onError: (error: Error) =>
      toast.error('Failed to delete user', { description: error.message }),
  })
}

export function useSetUserPassword(onSuccess?: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    ...userMutations.setPassword(),
    onSuccess: () => {
      invalidateUsers(queryClient)
      toast.success('Password updated')
      onSuccess?.()
    },
    onError: (error: Error) =>
      toast.error('Failed to update password', { description: error.message }),
  })
}
