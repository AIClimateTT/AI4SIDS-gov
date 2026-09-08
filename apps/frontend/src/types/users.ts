export type UserAccount = {
  user_id: string
  email: string
  first_name: string | null
  last_name: string | null
  role: string
  is_active: boolean
  last_login: string | null
}

export type UserWriteInput = {
  email: string
  first_name?: string | null
  last_name?: string | null
}
