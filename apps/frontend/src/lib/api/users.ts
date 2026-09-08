import { apiClient } from '@/lib/api/client'
import { withApiError } from '@/lib/api/errors'
import type { UserAccount, UserWriteInput } from '@/types/users'

export async function getUsers(): Promise<UserAccount[]> {
  return withApiError(async () => {
    const { data } = await apiClient.get<UserAccount[]>('/users')
    return data
  })
}

export async function createUser(payload: UserWriteInput): Promise<UserAccount> {
  return withApiError(async () => {
    const { data } = await apiClient.post<UserAccount>('/users', payload)
    return data
  })
}

export async function updateUser(
  userId: string,
  payload: UserWriteInput,
): Promise<UserAccount> {
  return withApiError(async () => {
    const { data } = await apiClient.patch<UserAccount>(`/users/${userId}`, payload)
    return data
  })
}

export async function activateUser(userId: string): Promise<UserAccount> {
  return withApiError(async () => {
    const { data } = await apiClient.post<UserAccount>(`/users/${userId}/activate`)
    return data
  })
}

export async function deactivateUser(userId: string): Promise<UserAccount> {
  return withApiError(async () => {
    const { data } = await apiClient.post<UserAccount>(`/users/${userId}/deactivate`)
    return data
  })
}

export async function deleteUser(userId: string): Promise<void> {
  return withApiError(async () => {
    await apiClient.delete(`/users/${userId}`)
  })
}
