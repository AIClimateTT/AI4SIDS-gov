export type UserAccount = {
  user_id: string
  email: string
  first_name: string | null
  last_name: string | null
  role: string
  corporation: string | null
  is_active: boolean
  last_login: string | null
  has_password: boolean
}

export type UserWriteInput = {
  email: string
  first_name?: string | null
  last_name?: string | null
  corporation?: string | null
}

export type UserCreateInput = UserWriteInput & {
  password: string
  role: 'dmu' | 'admin' | 'corp'
}
