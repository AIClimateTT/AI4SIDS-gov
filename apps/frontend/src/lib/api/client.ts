import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import { getAccessToken } from '@/lib/auth/storage'
import {
  AuthUnavailableError,
  forceLogout,
  proactiveRefresh,
  reactiveRefresh,
} from '@/lib/auth/refresh'

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

type RetriableConfig = InternalAxiosRequestConfig & {
  _retriedAfterRefresh?: boolean
}

let _api: AxiosInstance | null = null

function getApi(): AxiosInstance {
  if (!_api) {
    _api = axios.create({
      baseURL,
      headers: { 'Content-Type': 'application/json' },
      timeout: 120000,
    })

    _api.interceptors.request.use(async (config) => {
      if (config.data instanceof FormData) {
        delete config.headers['Content-Type']
      }
      const token = await proactiveRefresh(
        getAccessToken(),
        String(config.url ?? ''),
      )
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })

    _api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const original = (error.config ?? {}) as RetriableConfig
        if (error.response?.status === 401 && !original._retriedAfterRefresh) {
          try {
            const refreshed = await reactiveRefresh()
            original._retriedAfterRefresh = true
            original.headers = original.headers ?? {}
            original.headers.Authorization = `Bearer ${refreshed}`
            return getApi().request(original)
          } catch (refreshError) {
            if (!(refreshError instanceof AuthUnavailableError)) forceLogout()
            return Promise.reject(error)
          }
        }
        return Promise.reject(error)
      },
    )
  }

  return _api
}

/**
 * Shared HTTP client. Bearer tokens are attached from the auth session.
 * Login / OTP / refresh / logout use raw fetch, not this instance.
 */
export const apiClient = new Proxy({} as AxiosInstance, {
  get(_, prop) {
    const api = getApi()
    const value = api[prop as keyof AxiosInstance]
    return typeof value === 'function'
      ? (value as (...args: unknown[]) => unknown).bind(api)
      : value
  },
})
