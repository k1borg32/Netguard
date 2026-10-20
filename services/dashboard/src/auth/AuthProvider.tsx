import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { clearTokens, getRefreshToken, onSessionExpired, refreshTokens } from '../api/client'
import { AuthContext, type AuthState, type AuthStatus } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthStatus>(() => (getRefreshToken() ? 'loading' : 'anonymous'))
  const [user, setUser] = useState<authApi.User | null>(null)
  const [expired, setExpired] = useState(false)

  const signOutLocally = useCallback(() => {
    clearTokens()
    queryClient.clear()
    setUser(null)
    setStatus('anonymous')
  }, [queryClient])

  useEffect(() => {
    onSessionExpired(() => {
      setExpired(true)
      signOutLocally()
    })
  }, [signOutLocally])

  // After a page reload only the refresh token is left: trade it for a new pair.
  useEffect(() => {
    if (status !== 'loading') return
    let cancelled = false
    ;(async () => {
      try {
        if (!(await refreshTokens())) throw new Error('refresh failed')
        const me = await authApi.getMe()
        if (!cancelled) {
          setUser(me)
          setStatus('authenticated')
        }
      } catch {
        if (!cancelled) signOutLocally()
      }
    })()
    return () => {
      cancelled = true
    }
  }, [status, signOutLocally])

  const login = useCallback(async (username: string, password: string) => {
    await authApi.login(username, password)
    const me = await authApi.getMe()
    setExpired(false)
    setUser(me)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setExpired(false)
    signOutLocally()
  }, [signOutLocally])

  const value = useMemo<AuthState>(
    () => ({ status, user, expired, login, logout }),
    [status, user, expired, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
