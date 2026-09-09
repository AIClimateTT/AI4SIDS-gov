export const API_BASE_URL =
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_API_URL ||
  'http://localhost:8000'
export const ACCESS_TOKEN_KEY = 'auth_token'
export const REFRESH_TOKEN_KEY = 'refresh_token'
export const STORAGE_PREF_KEY = 'auth_storage'
export const STORED_AT_KEY = 'auth_stored_at'
export const TOKEN_EXPIRY_BUFFER_SECONDS = 60
export const AUTH_ENDPOINT_PREFIX = '/auth/'
export const AUTH_CHANGE_EVENT = 'auth-change'
export const TIMED_SESSION_MAX_AGE_MS = 36 * 60 * 60 * 1000
export const OTP_EMAIL_KEY = 'otp_email'
export const OTP_REDIRECT_KEY = 'otp_redirect'
