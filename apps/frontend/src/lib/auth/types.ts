export type JwtPayload = {
  sub: string
  role: string
  email?: string
  first_name?: string
  last_name?: string
  corporation?: string
  exp?: number
}

export type AuthTokenResponse = {
  access_token: string
  refresh_token: string
  token_type?: string
}

export type Session = {
  userId: string
  email: string
  role: string
  firstName: string
  lastName: string
  corporation: string
  accessToken: string
  refreshToken: string
}

export function mapPayloadToSession(
  payload: Record<string, unknown>,
  tokens: AuthTokenResponse,
): Session {
  return {
    userId: payload.sub as string,
    role: (payload.role as string) ?? 'member',
    email: (payload.email as string) ?? '',
    firstName: (payload.first_name as string) ?? '',
    lastName: (payload.last_name as string) ?? '',
    corporation: (payload.corporation as string) ?? '',
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  }
}
