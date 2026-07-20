import axios, { type AxiosInstance } from 'axios'

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

let _api: AxiosInstance | null = null

function getApi(): AxiosInstance {
  if (!_api) {
    _api = axios.create({
      baseURL,
      headers: { 'Content-Type': 'application/json' },
      timeout: 120000,
    })

    _api.interceptors.request.use((config) => {
      if (config.data instanceof FormData) {
        delete config.headers['Content-Type']
      }
      return config
    })
  }

  return _api
}

/**
 * Shared HTTP client. Fetchers currently return mocks; swap those
 * implementations to `apiClient` calls when the backend is wired.
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
