import { api, clearTokens, getRefreshToken, setTokens, type TokenPair } from './client'

export type UserRole = 'user' | 'admin'

export interface User {
  user_id: string
  username: string
  role: UserRole
}

export async function login(username: string, password: string): Promise<void> {
  const pair = await api<TokenPair>('/auth/login', {
    method: 'POST',
    body: { username, password },
    auth: false,
  })
  setTokens(pair)
}

export function getMe(): Promise<User> {
  return api<User>('/auth/me')
}

/** Ends the refresh session on the server; local tokens are cleared even if that fails. */
export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken()
  try {
    if (refreshToken) {
      await api<void>('/auth/logout', {
        method: 'POST',
        auth: false,
        headers: { Authorization: `Bearer ${refreshToken}` },
      })
    }
  } catch {
    // Session may already be gone; nothing to do.
  } finally {
    clearTokens()
  }
}
