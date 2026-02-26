import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, isAuthenticated, getToken, refreshToken } from '../services/auth'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  // TEMPORARILY DISABLED: Bypass authentication for development
  const BYPASS_AUTH = true

  const [user, setUser] = useState(BYPASS_AUTH ? {
    email: 'dev@airex.local',
    role: 'operator',
    tenantId: '00000000-0000-0000-0000-000000000000',
    userId: 'dev-user',
    displayName: 'Dev User'
  } : null)
  const [token, setToken] = useState(() => BYPASS_AUTH ? 'dev-token' : getToken())
  const [loading, setLoading] = useState(() => {
    // When auth is bypassed, start with loading=false immediately
    if (BYPASS_AUTH) return false
    return true
  })

  useEffect(() => {
    if (BYPASS_AUTH) return

    if (isAuthenticated()) {
      try {
        const t = getToken()
        if (t) {
          const payload = JSON.parse(atob(t.split('.')[1]))
          setUser({
            email: payload.sub,
            role: payload.role || 'operator',
            tenantId: payload.tenant_id,
            userId: payload.user_id,
          })
          setToken(t)
        }
      } catch {
        apiLogout()
      }
    }
    setLoading(false)
  }, [BYPASS_AUTH])

  const login = useCallback(async ({ email, password }) => {
    const res = await apiLogin({ email, password })
    const payload = JSON.parse(atob(res.access_token.split('.')[1]))
    setUser({
      email: payload.sub,
      role: payload.role || 'operator',
      tenantId: payload.tenant_id,
      userId: payload.user_id,
    })
    setToken(res.access_token)
    if (payload.tenant_id) {
      localStorage.setItem('tenant_id', payload.tenant_id)
    }
    return res
  }, [])

  const logout = useCallback(() => {
    apiLogout()
    setUser(null)
    setToken(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const res = await refreshToken()
      const payload = JSON.parse(atob(res.access_token.split('.')[1]))
      setUser({
        email: payload.sub,
        role: payload.role || 'operator',
        tenantId: payload.tenant_id,
        userId: payload.user_id,
      })
      setToken(res.access_token)
    } catch {
      logout()
    }
  }, [logout])

  // TEMPORARILY DISABLED: Always return authenticated
  const isAuth = BYPASS_AUTH ? true : !!token

  return (
    <AuthContext.Provider value={{ 
      user, 
      token, 
      loading, 
      login, 
      logout, 
      refresh, 
      isAuthenticated: isAuth
    }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- useAuth hook must co-locate with AuthProvider
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
